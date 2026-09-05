"""
시세 조회 및 투자 지표 계산 모듈

DuckDB에서 관심단지의 매매·전세 데이터를 조회하고,
전세가율, 전고점 대비, 갭 등 투자 지표를 계산한다.
"""

from datetime import datetime

import duckdb

from src.config import DB_PATH
from src.utils.address import get_sigungu_lookup_keyword, parse_sigungu


VALID_ACTIVE_TRADE_FILTER = (
    "(해제사유발생일 IS NULL OR CAST(해제사유발생일 AS VARCHAR) IN ('', 'None'))"
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
    return max(1, datetime.now().year - 건축년도)


def get_tracking_data(watchlist: list[dict]) -> list[dict]:
    """
    관심단지 목록을 받아 트래킹 데이터를 조회·계산한다.

    Returns:
        관심단지별 트래킹 데이터 딕셔너리 리스트
    """
    con = _get_connection()
    results = []

    for item in watchlist:
        단지명 = item["단지명"]
        시군구_full = item["시군구"]
        전용면적 = item["전용면적"]

        row = _build_tracking_row(con, 단지명, 시군구_full, 전용면적)
        results.append(row)

    con.close()
    return results


def _build_tracking_row(con, 단지명: str, 시군구_full: str, 전용면적: float) -> dict:
    """단지 하나의 트래킹 데이터를 조회·계산한다."""
    addr = _parse_시군구(시군구_full)
    평형 = _calc_평형(전용면적)

    # ── 건축년도·연식 ──
    건축년도_row = con.execute("""
        SELECT 건축년도 FROM 매매
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 1
        LIMIT 1
    """, [단지명, 전용면적]).fetchone()
    건축년도 = 건축년도_row[0] if 건축년도_row else None
    연식 = _calc_연식(건축년도) if 건축년도 else None

    # ── 세대수 (공동주택_전국 매칭) ──
    세대수 = _get_세대수(con, 단지명, 시군구_full)

    # ── 매매 시세 ──
    최근매매, 최근매매_거래유형 = _get_latest_price(con, 단지명, 전용면적)
    전월매매 = _get_prev_month_price(con, 단지명, 전용면적)
    매매전월대비 = (최근매매 - 전월매매) if (최근매매 and 전월매매) else None

    # ── 전세 시세 ──
    최근전세 = _get_latest_jeonse(con, 단지명, 전용면적)
    전월전세 = _get_prev_month_jeonse(con, 단지명, 전용면적)
    전세전월대비 = (최근전세 - 전월전세) if (최근전세 and 전월전세) else None

    # ── 투자 지표 ──
    갭 = (최근매매 - 최근전세) if (최근매매 and 최근전세) else None
    전월갭 = (전월매매 - 전월전세) if (전월매매 and 전월전세) else None
    갭전월대비 = (갭 - 전월갭) if (갭 is not None and 전월갭 is not None) else None

    전세가율 = round(최근전세 / 최근매매 * 100, 1) if (최근매매 and 최근전세) else None
    전월전세가율 = round(전월전세 / 전월매매 * 100, 1) if (전월매매 and 전월전세) else None
    전세가율전월대비 = round(전세가율 - 전월전세가율, 1) if (전세가율 is not None and 전월전세가율 is not None) else None

    전고점 = _get_전고점(con, 단지명, 전용면적)
    전고점대비 = round((최근매매 / 전고점 - 1) * 100, 1) if (최근매매 and 전고점) else None

    # ── 비고 ──
    비고 = "직거래" if 최근매매_거래유형 == "직거래" else None

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
        "최근매매가": 최근매매,
        "매매전월대비": 매매전월대비,
        "최근전세가": 최근전세,
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

def _get_세대수(con, 단지명: str, 시군구_full: str) -> int | None:
    """공동주택_전국 테이블에서 세대수를 매칭한다."""
    keyword = get_sigungu_lookup_keyword(시군구_full)
    row = con.execute("""
        SELECT 세대수 FROM 공동주택_전국
        WHERE 단지명 = ? AND 주소 LIKE ?
        LIMIT 1
    """, [단지명, f"%{keyword}%"]).fetchone()
    return row[0] if row else None

def _get_latest_price(con, 단지명: str, 전용면적: float) -> tuple[int | None, str | None]:
    """매매 테이블에서 최근 거래가와 거래유형을 조회한다."""
    row = con.execute(f"""
        SELECT 거래금액, 거래유형 FROM 매매
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 1
          AND {VALID_ACTIVE_TRADE_FILTER}
        ORDER BY 계약년월 DESC, 계약일 DESC
        LIMIT 1
    """, [단지명, 전용면적]).fetchone()
    return (row[0], row[1]) if row else (None, None)


def _get_prev_month_price(con, 단지명: str, 전용면적: float) -> int | None:
    """매매 테이블에서 전월 최근 거래가를 조회한다."""
    # 최근 거래의 계약년월을 먼저 확인
    latest = con.execute(f"""
        SELECT MAX(계약년월) FROM 매매
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 1
          AND {VALID_ACTIVE_TRADE_FILTER}
    """, [단지명, 전용면적]).fetchone()

    if not latest or not latest[0]:
        return None

    latest_ym = latest[0]
    # 전월 계산
    if latest_ym % 100 == 1:
        prev_ym = (latest_ym // 100 - 1) * 100 + 12
    else:
        prev_ym = latest_ym - 1

    row = con.execute(f"""
        SELECT 거래금액 FROM 매매
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 1
          AND 계약년월 = ?
          AND {VALID_ACTIVE_TRADE_FILTER}
        ORDER BY 계약일 DESC
        LIMIT 1
    """, [단지명, 전용면적, prev_ym]).fetchone()
    return row[0] if row else None


def _get_latest_jeonse(con, 단지명: str, 전용면적: float) -> int | None:
    """전월세 테이블에서 최근 전세 보증금을 조회한다 (전세만, 월세 제외)."""
    row = con.execute("""
        SELECT 보증금 FROM 전월세
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 1
          AND 전월세구분 = '전세'
        ORDER BY 계약년월 DESC, 계약일 DESC
        LIMIT 1
    """, [단지명, 전용면적]).fetchone()
    return row[0] if row else None


def _get_prev_month_jeonse(con, 단지명: str, 전용면적: float) -> int | None:
    """전월세 테이블에서 전월 최근 전세 보증금을 조회한다."""
    latest = con.execute("""
        SELECT MAX(계약년월) FROM 전월세
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 1
          AND 전월세구분 = '전세'
    """, [단지명, 전용면적]).fetchone()

    if not latest or not latest[0]:
        return None

    latest_ym = latest[0]
    if latest_ym % 100 == 1:
        prev_ym = (latest_ym // 100 - 1) * 100 + 12
    else:
        prev_ym = latest_ym - 1

    row = con.execute("""
        SELECT 보증금 FROM 전월세
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 1
          AND 전월세구분 = '전세'
          AND 계약년월 = ?
        ORDER BY 계약일 DESC
        LIMIT 1
    """, [단지명, 전용면적, prev_ym]).fetchone()
    return row[0] if row else None


def _get_전고점(con, 단지명: str, 전용면적: float) -> int | None:
    """역대 최고 매매가를 조회한다."""
    row = con.execute(f"""
        SELECT MAX(거래금액) FROM 매매
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 1
          AND {VALID_ACTIVE_TRADE_FILTER}
    """, [단지명, 전용면적]).fetchone()
    return row[0] if row else None
