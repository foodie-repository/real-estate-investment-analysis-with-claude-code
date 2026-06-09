"""
수익률 계산 엔진

매수 시점과 보유 기간을 기준으로, 분석 대상 단지별
매매가·전세가·갭·매매차익·수익률을 계산한다.
"""

import duckdb

from src.config import DB_PATH
from src.utils.address import get_sigungu_lookup_keyword, parse_sigungu


VALID_ACTIVE_TRADE_FILTER = (
    "(해제사유발생일 IS NULL OR CAST(해제사유발생일 AS VARCHAR) IN ('', 'None'))"
)


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────

def _get_connection():
    """DuckDB read-only 연결을 반환한다."""
    return duckdb.connect(DB_PATH, read_only=True)


def _parse_시군구(시군구: str) -> dict:
    """시군구 문자열을 표준 구조로 분리한다."""
    return parse_sigungu(시군구)


def _calc_평형(전용면적: float) -> int:
    """전용면적(㎡) → 추정평형"""
    return round(전용면적 * 0.4)


def _add_years(ym: int, years: int) -> int:
    """YYYYMM에 N년을 더한다. 예: 202001 + 2 = 202201"""
    return (ym // 100 + years) * 100 + (ym % 100)


# ──────────────────────────────────────────────
# 데이터 조회
# ──────────────────────────────────────────────

def _get_세대수(con, 단지명: str, 시군구_full: str) -> int | None:
    """공동주택_전국 테이블에서 세대수를 매칭한다."""
    시군구_keyword = get_sigungu_lookup_keyword(시군구_full)
    row = con.execute("""
        SELECT 세대수 FROM 공동주택_전국
        WHERE 단지명 = ? AND 주소 LIKE ?
        LIMIT 1
    """, [단지명, f"%{시군구_keyword}%"]).fetchone()
    return row[0] if row else None


def _get_price_at(con, 단지명: str, 전용면적: float, target_ym: int,
                  table: str = "매매") -> int | None:
    """
    특정 시점의 가격을 조회한다.

    규칙:
    1. target_ym에 거래가 있으면 → 가장 최근 계약일의 거래 사용
    2. 없으면 → 가장 가까운 시점의 거래 사용 (전후 양방향)
    3. 가장 가까운 거래가 12개월 초과 차이 → None 반환

    Args:
        con: DuckDB 연결
        단지명: 아파트 단지명
        전용면적: 전용면적 (㎡)
        target_ym: 목표 년월 (YYYYMM 정수, 예: 202001)
        table: "매매" 또는 "전월세"

    Returns:
        가격 (만원) 또는 None
    """
    if table == "매매":
        price_col = "거래금액"
        extra_filter = (
            f"AND {VALID_ACTIVE_TRADE_FILTER} "
            "AND 거래유형 != '직거래'"
        )
    else:
        price_col = "보증금"
        extra_filter = "AND 전월세구분 = '전세'"

    # Phase 1: 해당 월 거래 확인
    row = con.execute(f"""
        SELECT {price_col} FROM {table}
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 1
          {extra_filter}
          AND 계약년월 = ?
        ORDER BY 계약일 DESC
        LIMIT 1
    """, [단지명, 전용면적, target_ym]).fetchone()

    if row:
        return row[0]

    # Phase 2: 가장 가까운 거래 찾기 (YYYYMM → 선형 월수 변환으로 정확한 차이 계산)
    row = con.execute(f"""
        SELECT {price_col},
               ABS((계약년월 // 100) * 12 + (계약년월 % 100)
                   - (? // 100) * 12 - (? % 100)) AS month_diff
        FROM {table}
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 1
          {extra_filter}
        ORDER BY month_diff ASC, 계약일 DESC
        LIMIT 1
    """, [target_ym, target_ym, 단지명, 전용면적]).fetchone()

    if row and row[1] <= 12:
        return row[0]

    return None


# ──────────────────────────────────────────────
# 단지 정보 조회
# ──────────────────────────────────────────────

def _get_단지정보(con, 단지명: str, 시군구_full: str, 전용면적: float) -> dict:
    """단지 기본 정보를 조회한다."""
    addr = _parse_시군구(시군구_full)
    평형 = _calc_평형(전용면적)
    세대수 = _get_세대수(con, 단지명, 시군구_full)

    # 건축년도: 매매 테이블에서 조회
    건축년도_row = con.execute("""
        SELECT 건축년도 FROM 매매
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 1
        LIMIT 1
    """, [단지명, 전용면적]).fetchone()
    건축년도 = 건축년도_row[0] if 건축년도_row else None

    return {
        "시도": addr["시도"],
        "시군구": addr["시군구"],
        "읍면동": addr["읍면동"],
        "단지명": 단지명,
        "전용면적": 전용면적,
        "평형": 평형,
        "세대수": 세대수,
        "건축년도": 건축년도,
    }


# ──────────────────────────────────────────────
# 수익률 계산
# ──────────────────────────────────────────────

def calculate_roi(targets: list[dict], purchase_ym: int,
                  periods: list[int] = None) -> list[dict]:
    """
    분석 대상 단지의 수익률을 계산한다.

    Args:
        targets: 분석 대상 목록 [{"시군구": ..., "단지명": ..., "전용면적": ...}, ...]
        purchase_ym: 매수 시점 (YYYYMM 정수, 예: 202001)
        periods: 보유 기간 목록 (년, 예: [2, 4]). 기본값 [2, 4]

    Returns:
        단지별 수익률 데이터 리스트
    """
    if periods is None:
        periods = [2, 4]

    con = _get_connection()
    results = []

    for target in targets:
        단지명 = target["단지명"]
        시군구_full = target["시군구"]
        전용면적 = target["전용면적"]

        # 1. 단지 기본 정보
        row = _get_단지정보(con, 단지명, 시군구_full, 전용면적)

        # 2. 매수 시점 가격 조회
        매수매매가 = _get_price_at(con, 단지명, 전용면적, purchase_ym, "매매")
        매수전세가 = _get_price_at(con, 단지명, 전용면적, purchase_ym, "전월세")

        # 갭 = 매매가 - 전세가 (매수 시점의 투자금)
        매수갭 = (매수매매가 - 매수전세가) if (매수매매가 and 매수전세가) else None

        row["매수_매매가"] = 매수매매가
        row["매수_전세가"] = 매수전세가
        row["매수_갭"] = 매수갭

        # 3. 기간별 수익률 계산
        for period in periods:
            sale_ym = _add_years(purchase_ym, period)
            p = f"{period}년"

            매도매매가 = _get_price_at(con, 단지명, 전용면적, sale_ym, "매매")
            매도전세가 = _get_price_at(con, 단지명, 전용면적, sale_ym, "전월세")

            # 갭 = 매도 시점의 매매가 - 전세가
            갭 = (매도매매가 - 매도전세가) if (매도매매가 and 매도전세가) else None

            # 매매차익 = 매도 매매가 - 매수 매매가
            매매차익 = (매도매매가 - 매수매매가) if (매도매매가 and 매수매매가) else None

            # 수익률 = 매매차익 ÷ 초기 갭 × 100
            # 갭이 음수(역전세)인 경우 부호가 역전되어 의미가 없으므로 None 처리
            수익률 = None
            if 매매차익 is not None and 매수갭 and 매수갭 > 0:
                수익률 = round(매매차익 / 매수갭 * 100, 1)

            row[f"{p}_매매가"] = 매도매매가
            row[f"{p}_전세가"] = 매도전세가
            row[f"{p}_갭"] = 갭
            row[f"{p}_매매차익"] = 매매차익
            row[f"{p}_수익률"] = 수익률

        results.append(row)

    con.close()
    return results
