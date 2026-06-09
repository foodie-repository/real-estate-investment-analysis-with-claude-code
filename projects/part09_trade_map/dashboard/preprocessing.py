"""
데이터 전처리 모듈 (SQL 푸시다운)

모든 전처리 로직을 DuckDB SQL로 실행하여 11M+ 행을 효율적으로 처리한다.
Python/pandas에는 필터링/집계된 결과만 반환한다.
"""
import math

from src.config import CURRENT_YEAR
from src.utils.address import (
    SIDO_SQL,
    SIGUNGU_SQL,
    EUPMYEONDONG_SQL,
    ROAD_ADDRESS_KEY_SQL,
)
from projects.part09_trade_map.dashboard.db import execute_query


# =============================================================================
# 전처리 SQL CTE (매매/전월세 공통 파생 컬럼 생성)
# =============================================================================
def build_preprocessing_cte(table_name: str) -> str:
    """
    전처리 CTE SQL을 생성한다.

    매매 또는 전월세 테이블에서 다음 파생 컬럼을 생성:
    - 시도, 시군구_parsed, 읍면동: 시군구 컬럼 파싱
    - 전용면적_구분: 5단계 분류 (한국부동산원 기준)
    - 추정평형, 평형대_구분: 7단계 분류
    - 계약연도: 계약년월에서 추출
    - 연식, 연식_구분: 건축년도 기반 계산
    - 도로명주소_key: 좌표 테이블 조인용 키
    """
    전월세_컬럼 = ", 전월세구분" if table_name == "전월세" else ""

    return f"""
    preprocessed AS (
        SELECT
            시군구 AS 시군구_원본,
            단지명,
            전용면적 AS 전용면적,
            계약년월,
            건축년도,
            도로명
            {전월세_컬럼},
            {ROAD_ADDRESS_KEY_SQL} AS 도로명주소_key,

            -- 주소 파싱
            {SIDO_SQL} AS 시도,
            {SIGUNGU_SQL} AS 시군구_parsed,
            {EUPMYEONDONG_SQL} AS 읍면동,

            -- 전용면적_구분 (한국부동산원 5단계)
            CASE
                WHEN 전용면적 <= 40 THEN '초소형'
                WHEN 전용면적 <= 60 THEN '소형'
                WHEN 전용면적 <= 85 THEN '중소형'
                WHEN 전용면적 <= 135 THEN '중대형'
                ELSE '대형'
            END AS 전용면적_구분,

            -- 추정평형 (전용면적 * 0.4)
            전용면적 * 0.4 AS 추정평형,

            -- 평형대_구분 (7단계)
            CASE
                WHEN 전용면적 * 0.4 < 10 THEN '10평 미만'
                WHEN 전용면적 * 0.4 < 20 THEN '10평대'
                WHEN 전용면적 * 0.4 < 30 THEN '20평대'
                WHEN 전용면적 * 0.4 < 40 THEN '30평대'
                WHEN 전용면적 * 0.4 < 50 THEN '40평대'
                WHEN 전용면적 * 0.4 < 60 THEN '50평대'
                ELSE '60평 이상'
            END AS 평형대_구분,

            -- 계약연도
            CAST(계약년월 / 100 AS INTEGER) AS 계약연도,

            -- 연식 (최소 1년)
            GREATEST({CURRENT_YEAR} - 건축년도, 1) AS 연식,

            -- 연식_구분
            CASE
                WHEN {CURRENT_YEAR} - 건축년도 < 5 THEN '5년 미만'
                WHEN {CURRENT_YEAR} - 건축년도 < 10 THEN '5~10년'
                WHEN {CURRENT_YEAR} - 건축년도 < 20 THEN '10~20년'
                WHEN {CURRENT_YEAR} - 건축년도 < 30 THEN '20~30년'
                ELSE '30년 이상'
            END AS 연식_구분,

            -- 도로명 (원본 확인용)
            도로명

        FROM {table_name}
        WHERE 시군구 IS NOT NULL
          AND 도로명 IS NOT NULL
          AND 도로명 != ''
          AND 건축년도 IS NOT NULL
          AND 건축년도 > 0
    )
    """


# =============================================================================
# 필터 조건 WHERE절 생성
# =============================================================================
def _add_in_filter(
    column: str,
    value: str | list[str],
    conditions: list,
    params: list,
) -> None:
    """단일값/리스트를 받아 '= ?' 또는 'IN (?, ...)' 조건을 추가한다."""
    if isinstance(value, list):
        placeholders = ", ".join("?" for _ in value)
        conditions.append(f"{column} IN ({placeholders})")
        params.extend(value)
    else:
        conditions.append(f"{column} = ?")
        params.append(value)


def build_where_clause(
    시도: str | list[str] | None = None,
    시군구: str | list[str] | None = None,
    읍면동: str | list[str] | None = None,
    연도_시작: int | None = None,
    연도_끝: int | None = None,
    면적대: list[str] | None = None,
    평형대: list[str] | None = None,
    전월세구분: str | None = None,
) -> tuple[str, list]:
    """필터 조건에 맞는 WHERE절과 파라미터를 생성한다."""
    conditions: list[str] = []
    params: list = []

    if 시도:
        _add_in_filter("시도", 시도, conditions, params)
    if 시군구:
        _add_in_filter("시군구_parsed", 시군구, conditions, params)
    if 읍면동:
        _add_in_filter("읍면동", 읍면동, conditions, params)

    if 연도_시작:
        conditions.append("계약연도 >= ?")
        params.append(연도_시작)
    if 연도_끝:
        conditions.append("계약연도 <= ?")
        params.append(연도_끝)

    if 면적대:
        _add_in_filter("전용면적_구분", 면적대, conditions, params)
    if 평형대:
        _add_in_filter("평형대_구분", 평형대, conditions, params)

    if 전월세구분:
        conditions.append("전월세구분 = ?")
        params.append(전월세구분)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    return where, params


# =============================================================================
# 공개 API 함수
# =============================================================================
def get_region_options(거래유형: str = "매매") -> dict:
    """
    시도 → 시군구 → 읍면동 계층 드롭다운 데이터를 반환한다.

    Parameters:
        거래유형: '매매', '전세', '월세' — 해당 테이블에서 지역 조회

    Returns:
        {시도: {시군구: [읍면동, ...]}}
    """
    table = "전월세" if 거래유형 in ("전세", "월세") else "매매"
    전월세_필터 = ""
    params = []
    if 거래유형 in ("전세", "월세"):
        전월세_필터 = "AND 전월세구분 = ?"
        params.append(거래유형)

    query = f"""
    WITH parsed AS (
        SELECT DISTINCT
            {SIDO_SQL} AS 시도,
            {SIGUNGU_SQL} AS 시군구,
            {EUPMYEONDONG_SQL} AS 읍면동
        FROM {table}
        WHERE 시군구 IS NOT NULL
        {전월세_필터}
    )
    SELECT 시도, 시군구, 읍면동
    FROM parsed
    WHERE 시도 != '' AND 시군구 != '' AND 읍면동 != ''
    ORDER BY 시도, 시군구, 읍면동
    """
    df = execute_query(query, params if params else None)

    result = {}
    for _, row in df.iterrows():
        시도 = row["시도"]
        시군구 = row["시군구"]
        읍면동 = row["읍면동"]

        if 시도 not in result:
            result[시도] = {}
        if 시군구 not in result[시도]:
            result[시도][시군구] = []
        if 읍면동 not in result[시도][시군구]:
            result[시도][시군구].append(읍면동)

    return result


def get_year_range(거래유형: str) -> tuple[int, int]:
    """
    테이블의 계약연도 범위를 반환한다.

    Parameters:
        거래유형: '매매', '전세', '월세'

    Returns:
        (최소연도, 최대연도) 튜플
    """
    table = "전월세" if 거래유형 in ("전세", "월세") else "매매"
    전월세_필터 = ""
    params = []
    if 거래유형 in ("전세", "월세"):
        전월세_필터 = "AND 전월세구분 = ?"
        params.append(거래유형)

    query = f"""
    SELECT
        MIN(CAST(계약년월 / 100 AS INTEGER)) AS min_year,
        MAX(CAST(계약년월 / 100 AS INTEGER)) AS max_year
    FROM {table}
    WHERE 계약년월 IS NOT NULL
    {전월세_필터}
    """
    df = execute_query(query, params if params else None)
    return int(df.iloc[0]["min_year"]), int(df.iloc[0]["max_year"])


def get_max_세대수() -> int:
    """
    공동주택_전국 테이블에서 최대 세대수를 조회하고 천단위 올림한 값을 반환한다.

    예: 최대 세대수가 10,859이면 → 11,000 반환
    """
    query = """
    SELECT MAX(세대수) AS max_세대수
    FROM 공동주택_전국
    WHERE 세대수 IS NOT NULL
    """
    df = execute_query(query)
    max_val = int(df.iloc[0]["max_세대수"])
    return math.ceil(max_val / 1000) * 1000
