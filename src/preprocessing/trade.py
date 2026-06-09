"""
아파트 실거래가 데이터 전처리 모듈

매매/전월세 데이터를 분석에 적합한 형태로 가공한다.
DuckDB SQL CTE로 구현하여 원본 데이터는 수정하지 않는다.
Part06~09 미니 프로젝트에서 이 모듈을 import해서 사용한다.

사용법:
    from src.preprocessing.trade import preprocess

    # 기본 전처리 (주소파싱, 면적분류, 평형환산, 연식계산)
    df = preprocess("매매")

    # 좌표 연결 포함
    df = preprocess("매매", steps=["주소파싱", "면적분류", "평형환산", "연식계산", "좌표연결"])

    # 전체 6항목
    df = preprocess("매매", steps="all")
"""

from datetime import datetime

import duckdb

from src.config import DB_PATH
from src.utils.address import (
    EUPMYEONDONG_SQL,
    ROAD_ADDRESS_KEY_SQL,
    SIDO_SQL,
    SIGUNGU_SQL,
)


# ──────────────────────────────────────────────
# 전처리 CTE 빌더 — 각 함수가 SQL CTE 조각을 반환한다
# ──────────────────────────────────────────────

def _cte_주소파싱(source: str) -> tuple[str, str]:
    """
    시군구 컬럼을 시도 / 시군구2 / 읍면동으로 분리한다.

    - 일반: "서울특별시 강남구 대치동" → 서울특별시 / 강남구 / 대치동
    - 이중시군구: "경기도 성남시 분당구 정자동" → 경기도 / 성남시 분당구 / 정자동
    - 세종: "세종특별자치시 한솔동" → 세종특별자치시 / 세종시 / 한솔동
    """
    return "주소파싱", f"""
        SELECT *,
            {SIDO_SQL} AS 시도,
            {SIGUNGU_SQL} AS 시군구2,
            {EUPMYEONDONG_SQL} AS 읍면동
        FROM {source}
    """


def _cte_면적분류(source: str) -> tuple[str, str]:
    """
    전용면적을 한국부동산원 기준 5단계로 분류한다.

    초소형(~40㎡), 소형(~60㎡), 중소형(~85㎡), 중대형(~135㎡), 대형(135㎡~)
    """
    return "면적분류", f"""
        SELECT *,
            CASE
                WHEN 전용면적 <= 40 THEN '초소형'
                WHEN 전용면적 <= 60 THEN '소형'
                WHEN 전용면적 <= 85 THEN '중소형'
                WHEN 전용면적 <= 135 THEN '중대형'
                ELSE '대형'
            END AS 면적분류
        FROM {source}
    """


def _cte_평형환산(source: str) -> tuple[str, str]:
    """
    전용면적을 추정평형과 평형대로 변환한다.

    추정평형 = floor(전용면적 × 0.4)
    평형대: 10평 미만, 10평대, 20평대, ..., 60평 이상
    """
    return "평형환산", f"""
        SELECT *,
            CAST(FLOOR(전용면적 * 0.4) AS INTEGER) AS 추정평형,
            CASE
                WHEN FLOOR(전용면적 * 0.4) < 10 THEN '10평 미만'
                WHEN FLOOR(전용면적 * 0.4) < 20 THEN '10평대'
                WHEN FLOOR(전용면적 * 0.4) < 30 THEN '20평대'
                WHEN FLOOR(전용면적 * 0.4) < 40 THEN '30평대'
                WHEN FLOOR(전용면적 * 0.4) < 50 THEN '40평대'
                WHEN FLOOR(전용면적 * 0.4) < 60 THEN '50평대'
                ELSE '60평 이상'
            END AS 평형대
        FROM {source}
    """


def _cte_연식계산(source: str) -> tuple[str, str]:
    """
    건축년도에서 연식과 연식구분을 계산한다.

    연식 = 현재년도 - 건축년도 (최소 1년)
    연식구분: 5년 미만, 5~10년, 10~20년, 20~30년, 30년 이상
    """
    year = datetime.now().year
    return "연식계산", f"""
        SELECT *,
            GREATEST(1, {year} - 건축년도) AS 연식,
            CASE
                WHEN {year} - 건축년도 < 5 THEN '5년 미만'
                WHEN {year} - 건축년도 < 10 THEN '5~10년'
                WHEN {year} - 건축년도 < 20 THEN '10~20년'
                WHEN {year} - 건축년도 < 30 THEN '20~30년'
                ELSE '30년 이상'
            END AS 연식구분
        FROM {source}
    """


def _cte_좌표연결(source: str) -> tuple[str, str]:
    """
    좌표 테이블과 시도+시군구+도로명 키로 조인하여 위경도를 연결한다.

    ROAD_ADDRESS_KEY_SQL = 좌표.도로명주소
    """
    return "좌표연결", f"""
        SELECT t.*, c.위도, c.경도
        FROM {source} t
        LEFT JOIN "좌표" c ON {ROAD_ADDRESS_KEY_SQL} = c.도로명주소
    """


def _cte_세대수연결(source: str) -> tuple[str, str]:
    """
    공동주택_전국 테이블과 조인하여 세대수를 연결한다.

    단지명 + 시군구 기준으로 매칭한다.
    """
    return "세대수연결", f"""
        SELECT t.*, h.세대수
        FROM {source} t
        LEFT JOIN (
            SELECT
                단지명,
                split_part(주소, ' ', 2) AS 시군구_area,
                MAX(CAST(세대수 AS INTEGER)) AS 세대수
            FROM "공동주택_전국"
            GROUP BY 단지명, split_part(주소, ' ', 2)
        ) h ON t.단지명 = h.단지명
            AND split_part(t.시군구, ' ', 2) = h.시군구_area
    """


# ──────────────────────────────────────────────
# 전처리 단계 매핑
# ──────────────────────────────────────────────

# 전처리 단계 (순서 중요 — 앞 단계가 뒤 단계의 입력이 된다)
STEPS = {
    "주소파싱": _cte_주소파싱,
    "면적분류": _cte_면적분류,
    "평형환산": _cte_평형환산,
    "연식계산": _cte_연식계산,
    "좌표연결": _cte_좌표연결,
    "세대수연결": _cte_세대수연결,
}

# 기본 전처리: 컬럼 변환 4항목 (조인 제외)
DEFAULT_STEPS = ["주소파싱", "면적분류", "평형환산", "연식계산"]

# 전체 전처리: 6항목 모두
ALL_STEPS = list(STEPS.keys())


# ──────────────────────────────────────────────
# 쿼리 빌더
# ──────────────────────────────────────────────

def build_query(table: str, steps: list[str] | None = None) -> str:
    """
    전처리 SQL 쿼리를 조립한다.

    Args:
        table: 원본 테이블명 ("매매" 또는 "전월세")
        steps: 적용할 전처리 단계 목록. None이면 기본 4항목.

    Returns:
        실행 가능한 SQL 쿼리 문자열
    """
    if steps is None:
        steps = DEFAULT_STEPS

    if not steps:
        return f'SELECT * FROM "{table}"'

    ctes = []
    source = f'"{table}"'  # 첫 CTE는 원본 테이블에서 읽는다

    for step_name in steps:
        if step_name not in STEPS:
            available = ", ".join(STEPS.keys())
            raise ValueError(
                f"알 수 없는 전처리 단계: '{step_name}'. "
                f"사용 가능: {available}"
            )

        cte_func = STEPS[step_name]
        cte_name, cte_sql = cte_func(source)
        ctes.append(f"{cte_name} AS ({cte_sql})")
        source = cte_name  # 다음 CTE는 이 CTE를 입력으로 사용

    query = "WITH " + ",\n".join(ctes) + f"\nSELECT * FROM {source}"
    return query


# ──────────────────────────────────────────────
# 메인 함수
# ──────────────────────────────────────────────

def preprocess(table: str, steps=None, con=None):
    """
    전처리된 데이터를 조회한다.

    Args:
        table: 원본 테이블명 ("매매" 또는 "전월세")
        steps: 적용할 전처리 단계 목록.
               None → 기본 4항목 (주소파싱, 면적분류, 평형환산, 연식계산)
               "all" → 전체 6항목 (좌표·세대수 연결 포함)
               리스트 → 지정한 항목만 적용
        con: DuckDB 커넥션. None이면 새로 생성하여 DataFrame으로 반환.

    Returns:
        con이 None이면 pandas DataFrame,
        con이 제공되면 DuckDB 결과 객체 (.df()로 DataFrame 변환 가능)
    """
    if steps == "all":
        steps = ALL_STEPS

    query = build_query(table, steps)

    # 커넥션이 제공되면 DuckDB 결과 반환 (호출자가 커넥션 관리)
    if con is not None:
        return con.sql(query)

    # 커넥션이 없으면 DataFrame으로 반환
    _con = duckdb.connect(DB_PATH, read_only=True)
    try:
        return _con.sql(query).df()
    finally:
        _con.close()
