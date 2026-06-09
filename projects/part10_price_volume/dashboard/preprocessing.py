"""
데이터 전처리 모듈

매매·전월세 데이터를 DuckDB SQL로 전처리하고,
필터 조건에 맞는 데이터를 조회한다.
"""
import pandas as pd

from src.utils.address import SIDO_SQL, SIGUNGU_SQL, EUPMYEONDONG_SQL
from projects.part10_price_volume.dashboard.db import execute_query


_PYEONG_VALUE_SQL = "FLOOR(전용면적 * 0.4)"
_PYEONG_BAND_SQL = f"""
CASE
    WHEN {_PYEONG_VALUE_SQL} < 10 THEN '10평 미만'
    WHEN {_PYEONG_VALUE_SQL} < 20 THEN '10평대'
    WHEN {_PYEONG_VALUE_SQL} < 30 THEN '20평대'
    WHEN {_PYEONG_VALUE_SQL} < 40 THEN '30평대'
    WHEN {_PYEONG_VALUE_SQL} < 50 THEN '40평대'
    WHEN {_PYEONG_VALUE_SQL} < 60 THEN '50평대'
    ELSE '60평 이상'
END
"""


def _and_filters(conditions: list[str]) -> str:
    """추가 조건 목록을 SQL AND 행으로 변환한다."""
    return "\n      ".join(f"AND {condition}" for condition in conditions)


def _매매_filters(직거래포함: bool) -> str:
    """매매 데이터의 직거래/취소거래 제외 조건."""
    conditions = []
    if not 직거래포함:
        conditions.append("(거래유형 IS NULL OR 거래유형 != '직거래')")
    conditions.append("(해제사유발생일 IS NULL OR 해제사유발생일 IN ('None', '-', ''))")
    return _and_filters(conditions)


def _전세_filters() -> str:
    """전월세 테이블에서 전세만 남기는 조건."""
    return _and_filters(["전월세구분 = '전세'"])


def _price_expr(amount_col: str) -> str:
    """만원 단위 거래금액/보증금을 억 단위 표시값으로 변환한다."""
    return f"ROUND({amount_col} / 10000.0, 1)"


# =============================================================================
# 지역 계층 옵션 조회
# =============================================================================
def get_region_options() -> dict:
    """
    시도 → 시군구 → 읍면동 → 단지 계층 데이터를 반환한다.
    매매 + 전월세 테이블을 합쳐서 전체 지역 목록을 구성한다.

    Returns:
        {시도: {시군구: {읍면동: [단지명, ...]}}}
    """
    query = f"""
    WITH combined AS (
        SELECT DISTINCT 시군구, 단지명
        FROM 매매
        WHERE 시군구 IS NOT NULL AND 단지명 IS NOT NULL
        UNION ALL
        SELECT DISTINCT 시군구, 단지명
        FROM 전월세
        WHERE 시군구 IS NOT NULL AND 단지명 IS NOT NULL
          AND 전월세구분 = '전세'
    ),
    parsed AS (
        SELECT DISTINCT
            {SIDO_SQL} AS 시도,
            {SIGUNGU_SQL} AS 시군구,
            {EUPMYEONDONG_SQL} AS 읍면동,
            단지명
        FROM combined
        WHERE 시군구 IS NOT NULL
    )
    SELECT 시도, 시군구, 읍면동, 단지명
    FROM parsed
    WHERE 시도 != '' AND 시군구 != '' AND 읍면동 != ''
    ORDER BY 시도, 시군구, 읍면동, 단지명
    """
    df = execute_query(query)

    result: dict = {}
    for _, row in df.iterrows():
        시도 = row["시도"]
        시군구 = row["시군구"]
        읍면동 = row["읍면동"]
        단지명 = row["단지명"]

        if 시도 not in result:
            result[시도] = {}
        if 시군구 not in result[시도]:
            result[시도][시군구] = {}
        if 읍면동 not in result[시도][시군구]:
            result[시도][시군구][읍면동] = []
        if 단지명 not in result[시도][시군구][읍면동]:
            result[시도][시군구][읍면동].append(단지명)

    return result


def get_date_range() -> tuple[int, int]:
    """
    매매·전월세 테이블의 계약년월 범위를 반환한다.

    Returns:
        (최소 계약년월, 최대 계약년월) — 예: (200601, 202509)
    """
    query = """
    SELECT
        MIN(계약년월) AS min_ym,
        MAX(계약년월) AS max_ym
    FROM (
        SELECT 계약년월 FROM 매매 WHERE 계약년월 IS NOT NULL
        UNION ALL
        SELECT 계약년월 FROM 전월세 WHERE 계약년월 IS NOT NULL AND 전월세구분 = '전세'
    )
    """
    df = execute_query(query)
    return int(df.iloc[0]["min_ym"]), int(df.iloc[0]["max_ym"])


# =============================================================================
# 개별 실거래가 조회 (뷰 1: 산점도용)
# =============================================================================
def get_individual_trades(
    시도: str,
    시군구: str,
    읍면동: list[str] | None = None,
    단지: list[str] | None = None,
    거래유형: str = "매매+전세",
    평형대: list[str] | None = None,
    시작년월: int | None = None,
    종료년월: int | None = None,
    직거래포함: bool = False,
) -> dict:
    """
    개별 거래 데이터를 조회한다. 매매와 전세를 각각 반환.

    Returns:
        {"매매": DataFrame, "전세": DataFrame}
        각 DataFrame 컬럼: 계약년월, 단지명, 전용면적, 가격_억, 층, 추정평형, 평형대
    """
    results = {}

    if 거래유형 in ("매매+전세", "매매만"):
        results["매매"] = _query_매매(
            시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월, 직거래포함
        )

    if 거래유형 in ("매매+전세", "전세만"):
        results["전세"] = _query_전세(
            시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월
        )

    return results


def _build_where(
    시도: str,
    시군구: str,
    읍면동: list[str] | None,
    단지: list[str] | None,
    평형대: list[str] | None,
    시작년월: int | None,
    종료년월: int | None,
) -> tuple[str, list]:
    """공통 WHERE절을 생성한다."""
    conditions = [
        f"{SIDO_SQL} = ?",
        f"{SIGUNGU_SQL} = ?",
    ]
    params: list = [시도, 시군구]

    if 읍면동:
        placeholders = ", ".join("?" for _ in 읍면동)
        conditions.append(f"{EUPMYEONDONG_SQL} IN ({placeholders})")
        params.extend(읍면동)

    if 단지:
        placeholders = ", ".join("?" for _ in 단지)
        conditions.append(f"단지명 IN ({placeholders})")
        params.extend(단지)

    if 평형대:
        평형_conditions = []
        for p in 평형대:
            if p == "10평 미만":
                평형_conditions.append("FLOOR(전용면적 * 0.4) < 10")
            elif p == "10평대":
                평형_conditions.append("(FLOOR(전용면적 * 0.4) >= 10 AND FLOOR(전용면적 * 0.4) < 20)")
            elif p == "20평대":
                평형_conditions.append("(FLOOR(전용면적 * 0.4) >= 20 AND FLOOR(전용면적 * 0.4) < 30)")
            elif p == "30평대":
                평형_conditions.append("(FLOOR(전용면적 * 0.4) >= 30 AND FLOOR(전용면적 * 0.4) < 40)")
            elif p == "40평대":
                평형_conditions.append("(FLOOR(전용면적 * 0.4) >= 40 AND FLOOR(전용면적 * 0.4) < 50)")
            elif p == "50평대":
                평형_conditions.append("(FLOOR(전용면적 * 0.4) >= 50 AND FLOOR(전용면적 * 0.4) < 60)")
            elif p == "60평 이상":
                평형_conditions.append("FLOOR(전용면적 * 0.4) >= 60")
        if 평형_conditions:
            conditions.append(f"({' OR '.join(평형_conditions)})")

    if 시작년월:
        conditions.append("계약년월 >= ?")
        params.append(시작년월)
    if 종료년월:
        conditions.append("계약년월 <= ?")
        params.append(종료년월)

    return " AND ".join(conditions), params


def _query_매매(
    시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월, 직거래포함
):
    """매매 개별 거래 조회."""
    where, params = _build_where(시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월)
    return _query_individual("매매", "거래금액", where, params, _매매_filters(직거래포함))


def _query_전세(시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월):
    """전세 개별 거래 조회."""
    where, params = _build_where(시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월)
    return _query_individual("전월세", "보증금", where, params, _전세_filters())


def _query_individual(
    table: str,
    amount_col: str,
    where: str,
    params: list,
    extra_filters: str,
) -> pd.DataFrame:
    """매매/전세 개별 거래 조회의 공통 SQL."""
    query = f"""
    SELECT
        계약년월,
        단지명,
        전용면적,
        {_price_expr(amount_col)} AS 가격_억,
        층,
        CAST({_PYEONG_VALUE_SQL} AS INTEGER) AS 추정평형,
        {_PYEONG_BAND_SQL} AS 평형대
    FROM {table}
    WHERE {where}
      {extra_filters}
    ORDER BY 계약년월
    """
    return execute_query(query, params)


# =============================================================================
# 월별 집계 조회 (뷰 2: 선 그래프 + 거래량 막대)
# =============================================================================
def get_monthly_summary(
    시도: str,
    시군구: str,
    읍면동: list[str] | None = None,
    단지: list[str] | None = None,
    거래유형: str = "매매+전세",
    평형대: list[str] | None = None,
    시작년월: int | None = None,
    종료년월: int | None = None,
    직거래포함: bool = False,
) -> dict:
    """
    월별 중위가와 거래량을 조회한다.

    Returns:
        {"매매": DataFrame, "전세": DataFrame}
        각 DataFrame 컬럼: 계약년월, 중위가_억, 거래량
    """
    results = {}

    if 거래유형 in ("매매+전세", "매매만"):
        results["매매"] = _query_매매_monthly(
            시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월, 직거래포함
        )

    if 거래유형 in ("매매+전세", "전세만"):
        results["전세"] = _query_전세_monthly(
            시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월
        )

    return results


def _query_매매_monthly(
    시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월, 직거래포함
):
    """매매 월별 집계."""
    where, params = _build_where(시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월)
    return _query_monthly("매매", "거래금액", where, params, _매매_filters(직거래포함))


def _query_전세_monthly(시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월):
    """전세 월별 집계."""
    where, params = _build_where(시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월)
    return _query_monthly("전월세", "보증금", where, params, _전세_filters())


def _query_monthly(
    table: str,
    amount_col: str,
    where: str,
    params: list,
    extra_filters: str,
) -> pd.DataFrame:
    """매매/전세 월별 집계의 공통 SQL."""
    query = f"""
    SELECT
        계약년월,
        ROUND(MEDIAN({amount_col}) / 10000.0, 1) AS 중위가_억,
        COUNT(*) AS 거래량
    FROM {table}
    WHERE {where}
      {extra_filters}
    GROUP BY 계약년월
    ORDER BY 계약년월
    """
    return execute_query(query, params)


# =============================================================================
# 요약 정보 조회
# =============================================================================
def get_summary_stats(
    시도: str,
    시군구: str,
    읍면동: list[str] | None = None,
    단지: list[str] | None = None,
    평형대: list[str] | None = None,
    시작년월: int | None = None,
    종료년월: int | None = None,
    직거래포함: bool = False,
) -> dict:
    """
    선택 조건에 대한 요약 통계를 반환한다.

    Returns:
        {
            "총거래건수": int,
            "최고가_억": float,
            "최저가_억": float,
            "최근거래": DataFrame (최근 3건),
        }
    """
    where, params = _build_where(시도, 시군구, 읍면동, 단지, 평형대, 시작년월, 종료년월)
    extra_filters = _매매_filters(직거래포함)

    # 집계 쿼리
    stats_query = f"""
    SELECT
        COUNT(*) AS 총거래건수,
        ROUND(MAX(거래금액) / 10000.0, 1) AS 최고가_억,
        ROUND(MIN(거래금액) / 10000.0, 1) AS 최저가_억
    FROM 매매
    WHERE {where}
      {extra_filters}
    """
    stats_df = execute_query(stats_query, params)

    # 최근 거래 3건
    recent_query = f"""
    SELECT
        계약년월,
        단지명,
        전용면적,
        ROUND(거래금액 / 10000.0, 1) AS 가격_억,
        층
    FROM 매매
    WHERE {where}
      {extra_filters}
    ORDER BY 계약년월 DESC, 거래금액 DESC
    LIMIT 3
    """
    recent_df = execute_query(recent_query, params.copy())

    row = stats_df.iloc[0]
    총건수 = int(row["총거래건수"]) if pd.notna(row["총거래건수"]) else 0
    최고 = float(row["최고가_억"]) if pd.notna(row["최고가_억"]) else 0
    최저 = float(row["최저가_억"]) if pd.notna(row["최저가_억"]) else 0
    return {
        "총거래건수": 총건수,
        "최고가_억": 최고,
        "최저가_억": 최저,
        "최근거래": recent_df,
    }
