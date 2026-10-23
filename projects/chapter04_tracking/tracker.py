"""
시세 조회 및 투자 지표 계산 모듈

DuckDB에서 관심단지의 매매·전세 데이터를 조회하고,
전세가율, 전고점 대비, 갭 등 투자 지표를 계산한다.
"""

from datetime import datetime

import duckdb

from src.config import CURRENT_YEAR, DB_PATH
from src.utils.address import get_sigungu_lookup_keyword, parse_sigungu


VALID_ACTIVE_TRADE_FILTER = (
    "(해제사유발생일 IS NULL OR CAST(해제사유발생일 AS VARCHAR) IN ('', 'None', '-'))"
)


def _get_connection():
    return duckdb.connect(DB_PATH, read_only=True)


def _parse_시군구(시군구: str) -> dict:
    """시군구 문자열을 표준 구조로 분리한다."""
    return parse_sigungu(시군구)


def _calc_평형(전용면적: float) -> int:
    """전용면적(㎡) → 추정평형"""
    return round(전용면적 * 0.4)


def _calc_연식(건축년도: int) -> int:
    """건축년도 → 연식 (최소 1년)"""
    return max(1, CURRENT_YEAR - 건축년도)


def get_tracking_data(watchlist: list[dict]) -> list[dict]:
    """
    관심단지 목록을 받아 트래킹 데이터를 조회·계산한다.

    Returns:
        관심단지별 트래킹 데이터 딕셔너리 리스트
    """
    con = _get_connection()
    try:
        results = []
        for item in watchlist:
            단지명 = item["단지명"]
            시군구_full = item["시군구"]
            전용면적 = item["전용면적"]
            results.append(
                _build_tracking_row(con, 단지명, 시군구_full, 전용면적)
            )
        return results
    finally:
        con.close()


def _build_tracking_row(con, 단지명: str, 시군구_full: str, 전용면적: float) -> dict:
    """단지 하나의 트래킹 데이터를 조회·계산한다."""
    addr = _parse_시군구(시군구_full)
    평형 = _calc_평형(전용면적)

    # ── 건축년도·연식 ──
    건축년도_row = con.execute("""
        SELECT 건축년도 FROM 매매
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 0.001 AND (? IS NULL OR 시군구 = ?)
        LIMIT 1
    """, [단지명, 전용면적, 시군구_full, 시군구_full]).fetchone()
    건축년도 = 건축년도_row[0] if 건축년도_row else None
    연식 = _calc_연식(건축년도) if 건축년도 else None

    # ── 세대수 (공동주택_전국 매칭) ──
    세대수 = _get_세대수(con, 단지명, 시군구_full)

    기준월 = _get_latest_common_month(con, 단지명, 전용면적, 시군구_full)
    전월 = _previous_month(기준월) if 기준월 else None
    데이터최신월 = _get_latest_data_month(con, 단지명, 전용면적, 시군구_full)

    # ── 매매 시세 ──
    매매통계 = _get_sale_stats(con, 단지명, 전용면적, 기준월, 시군구_full)
    전월매매통계 = _get_sale_stats(con, 단지명, 전용면적, 전월, 시군구_full)
    최근매매 = 매매통계["중앙값"]
    전월매매 = 전월매매통계["중앙값"]
    매매전월대비 = (최근매매 - 전월매매) if (최근매매 and 전월매매) else None

    # ── 전세 시세 ──
    전세통계 = _get_jeonse_stats(con, 단지명, 전용면적, 기준월, 시군구_full)
    전월전세통계 = _get_jeonse_stats(con, 단지명, 전용면적, 전월, 시군구_full)
    최근전세 = 전세통계["신규중앙값"]
    전월전세 = 전월전세통계["신규중앙값"]
    전세전월대비 = (최근전세 - 전월전세) if (최근전세 and 전월전세) else None

    # ── 투자 지표 ──
    갭 = (최근매매 - 최근전세) if (최근매매 and 최근전세) else None
    전월갭 = (전월매매 - 전월전세) if (전월매매 and 전월전세) else None
    갭전월대비 = (갭 - 전월갭) if (갭 is not None and 전월갭 is not None) else None

    전세가율 = round(최근전세 / 최근매매 * 100, 1) if (최근매매 and 최근전세) else None
    전월전세가율 = round(전월전세 / 전월매매 * 100, 1) if (전월매매 and 전월전세) else None
    전세가율전월대비 = round(전세가율 - 전월전세가율, 1) if (전세가율 is not None and 전월전세가율 is not None) else None

    전고점 = _get_전고점(con, 단지명, 전용면적, 시군구_full)
    전고점대비 = round((최근매매 / 전고점 - 1) * 100, 1) if (최근매매 and 전고점) else None
    잠정수치 = _is_provisional(기준월)
    if 기준월 is None:
        비고 = "동일 기준월의 중개 매매·신규 전세 없음"
    else:
        notes = []
        if 잠정수치:
            notes.append("최근 1~2개월 잠정 수치")
        if _needs_data_refresh(데이터최신월):
            notes.append(f"데이터 최신월 {데이터최신월}: 갱신 필요")
        비고 = "; ".join(notes) or None

    return {
        "시도": addr["시도"],
        "시군구": addr["시군구"],
        "읍면동": addr["읍면동"],
        "단지명": 단지명,
        "전용면적": 전용면적,
        "평형": 평형,
        "세대수": 세대수,
        "건축년도": 건축년도,
        "연식": 연식,
        "기준월": 기준월,
        "데이터최신월": 데이터최신월,
        "전월기준월": 전월,
        "잠정수치": 잠정수치,
        "최근매매가": 최근매매,
        "매매거래건수": 매매통계["거래건수"],
        "직거래제외건수": 매매통계["직거래건수"],
        "매매전월대비": 매매전월대비,
        "최근전세가": 최근전세,
        "신규전세거래건수": 전세통계["신규건수"],
        "갱신전세가": 전세통계["갱신중앙값"],
        "갱신전세거래건수": 전세통계["갱신건수"],
        "전세전월대비": 전세전월대비,
        "매매전세갭": 갭,
        "갭전월대비": 갭전월대비,
        "전세가율": 전세가율,
        "전세가율전월대비": 전세가율전월대비,
        "전고점": 전고점,
        "전고점대비": 전고점대비,
        "전월매매": 전월매매,
        "전월전세": 전월전세,
        "전월갭": 전월갭,
        "전월전세가율": 전월전세가율,
        "비고": 비고,
    }


# ──────────────────────────────────────────────
# 데이터 조회 함수
# ──────────────────────────────────────────────

def _previous_month(계약년월: int) -> int:
    """YYYYMM 정수에서 바로 전 달을 계산한다."""
    if 계약년월 % 100 == 1:
        return (계약년월 // 100 - 1) * 100 + 12
    return 계약년월 - 1


def _current_year_month() -> int:
    """현재 연월을 YYYYMM 정수로 반환한다."""
    now = datetime.now()
    return now.year * 100 + now.month


def _get_latest_common_month(con, 단지명: str, 전용면적: float, 시군구_full: str | None = None) -> int | None:
    """중개 매매와 신규 전세가 모두 존재하는 가장 최근 계약월을 조회한다."""
    row = con.execute(f"""
        WITH 매매월 AS (
            SELECT DISTINCT 계약년월
            FROM 매매
            WHERE 단지명 = ? AND ABS(전용면적 - ?) < 0.001 AND (? IS NULL OR 시군구 = ?)
              AND {VALID_ACTIVE_TRADE_FILTER}
              AND 거래유형 = '중개거래'
        ),
        전세월 AS (
            SELECT DISTINCT 계약년월
            FROM 전월세
            WHERE 단지명 = ? AND ABS(전용면적 - ?) < 0.001 AND (? IS NULL OR 시군구 = ?)
              AND 전월세구분 = '전세'
              AND 계약구분 = '신규'
        )
        SELECT MAX(매매월.계약년월)
        FROM 매매월
        INNER JOIN 전세월 USING (계약년월)
    """, [단지명, 전용면적, 시군구_full, 시군구_full, 단지명, 전용면적, 시군구_full, 시군구_full]).fetchone()
    return row[0] if row and row[0] else None


def _get_latest_data_month(
    con,
    단지명: str,
    전용면적: float,
    시군구_full: str | None = None,
) -> int | None:
    """해당 주택형의 매매·전세 자료에 수록된 가장 최근 계약월을 조회한다."""
    row = con.execute(f"""
        SELECT MAX(계약년월)
        FROM (
            SELECT 계약년월
            FROM 매매
            WHERE 단지명 = ? AND ABS(전용면적 - ?) < 0.001 AND (? IS NULL OR 시군구 = ?)
              AND {VALID_ACTIVE_TRADE_FILTER}
            UNION ALL
            SELECT 계약년월
            FROM 전월세
            WHERE 단지명 = ? AND ABS(전용면적 - ?) < 0.001 AND (? IS NULL OR 시군구 = ?)
              AND 전월세구분 = '전세'
        )
    """, [단지명, 전용면적, 시군구_full, 시군구_full, 단지명, 전용면적, 시군구_full, 시군구_full]).fetchone()
    return row[0] if row and row[0] else None


def _is_provisional(기준월: int | None) -> bool:
    """기준월이 실행 시점의 현재월 또는 바로 전 달인지 확인한다."""
    if 기준월 is None:
        return False
    현재월 = _current_year_month()
    return 기준월 in {현재월, _previous_month(현재월)}


def _needs_data_refresh(데이터최신월: int | None) -> bool:
    """데이터 최신월이 실행 시점의 바로 전 달보다 오래됐는지 확인한다."""
    if 데이터최신월 is None:
        return False
    return 데이터최신월 < _previous_month(_current_year_month())


def _get_sale_stats(
    con,
    단지명: str,
    전용면적: float,
    계약년월: int | None,
    시군구_full: str | None = None,
) -> dict:
    """지정한 계약월의 중개 매매 중앙값·건수와 직거래 건수를 조회한다."""
    if 계약년월 is None:
        return {"중앙값": None, "거래건수": 0, "직거래건수": 0}
    row = con.execute(f"""
        SELECT
            MEDIAN(거래금액) FILTER (WHERE 거래유형 = '중개거래'),
            COUNT(*) FILTER (WHERE 거래유형 = '중개거래'),
            COUNT(*) FILTER (WHERE 거래유형 = '직거래')
        FROM 매매
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 0.001 AND (? IS NULL OR 시군구 = ?)
          AND 계약년월 = ?
          AND {VALID_ACTIVE_TRADE_FILTER}
    """, [단지명, 전용면적, 시군구_full, 시군구_full, 계약년월]).fetchone()
    return {
        "중앙값": row[0] if row else None,
        "거래건수": row[1] if row else 0,
        "직거래건수": row[2] if row else 0,
    }


def _get_jeonse_stats(
    con,
    단지명: str,
    전용면적: float,
    계약년월: int | None,
    시군구_full: str | None = None,
) -> dict:
    """지정한 계약월의 신규·갱신 전세 중앙값과 거래 건수를 조회한다."""
    if 계약년월 is None:
        return {
            "신규중앙값": None,
            "신규건수": 0,
            "갱신중앙값": None,
            "갱신건수": 0,
        }
    row = con.execute("""
        SELECT
            MEDIAN(보증금) FILTER (WHERE 계약구분 = '신규'),
            COUNT(*) FILTER (WHERE 계약구분 = '신규'),
            MEDIAN(보증금) FILTER (WHERE 계약구분 = '갱신'),
            COUNT(*) FILTER (WHERE 계약구분 = '갱신')
        FROM 전월세
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 0.001 AND (? IS NULL OR 시군구 = ?)
          AND 계약년월 = ?
          AND 전월세구분 = '전세'
    """, [단지명, 전용면적, 시군구_full, 시군구_full, 계약년월]).fetchone()
    return {
        "신규중앙값": row[0] if row else None,
        "신규건수": row[1] if row else 0,
        "갱신중앙값": row[2] if row else None,
        "갱신건수": row[3] if row else 0,
    }


def _get_세대수(con, 단지명: str, 시군구_full: str) -> int | None:
    """공동주택_전국 테이블에서 세대수를 매칭한다."""
    keyword = get_sigungu_lookup_keyword(시군구_full)
    row = con.execute("""
        SELECT 세대수 FROM 공동주택_전국
        WHERE 단지명 = ? AND 주소 LIKE ?
        LIMIT 1
    """, [단지명, f"%{keyword}%"]).fetchone()
    return row[0] if row else None


def _get_전고점(con, 단지명: str, 전용면적: float, 시군구_full: str | None = None) -> int | None:
    """역대 최고 매매가를 조회한다."""
    row = con.execute(f"""
        SELECT MAX(거래금액) FROM 매매
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 0.001 AND (? IS NULL OR 시군구 = ?)
          AND {VALID_ACTIVE_TRADE_FILTER}
          AND 거래유형 = '중개거래'
    """, [단지명, 전용면적, 시군구_full, 시군구_full]).fetchone()
    return row[0] if row else None
