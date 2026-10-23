"""
피벗테이블 생성 모듈

거래 데이터를 집계하고 좌표/세대수 정보를 조인하여
지도 시각화용 피벗테이블을 생성한다.
"""
import pandas as pd
from projects.chapter08_trade_map.dashboard.db import execute_query, get_table_columns
from projects.chapter08_trade_map.dashboard.preprocessing import (
    build_preprocessing_cte, build_where_clause, get_source_expressions,
)


def generate_pivot_table(
    거래유형: str,
    시도: str | list[str],
    시군구: str | list[str] | None = None,
    읍면동: str | list[str] | None = None,
    연도_시작: int | None = None,
    연도_끝: int | None = None,
    면적대: list[str] | None = None,
    평형대: list[str] | None = None,
    세대수_범위: tuple[int, int] | None = None,
) -> pd.DataFrame:
    """
    필터 조건에 맞는 피벗테이블을 생성한다.

    CTE 파이프라인:
    1. preprocessed: 파생 컬럼 생성
    2. filtered: 사용자 필터 적용
    3. aggregated: 단지+면적대+연도별 거래량 집계
    4. joined: 좌표 테이블 조인 (시도+시군구+도로명 키 매칭)
    5. best_emd: 누락된 읍면동 보정
    6. best_coords: 가장 구체적인 도로명의 좌표 선택
    7. 세대수_lookup: 공동주택_전국에서 1:1 세대수 매칭

    Returns:
        DataFrame: 시도, 시군구, 읍면동, 단지명, 건축년도, 연식_구분,
                   전용면적_구분, 계약연도, 거래량, 세대수, 회전율, 경도, 위도
    """
    # 테이블 선택
    table = "전월세" if 거래유형 in ("전세", "월세") else "매매"
    전월세구분 = 거래유형 if 거래유형 in ("전세", "월세") else None
    source = get_source_expressions(table)

    # 공동주택 원자료는 수집 경로에 따라 단지명 컬럼 구성이 다르다.
    # 독자용 DB의 단일 단지명과 집필용 DB의 출처별 단지명을 모두 정확 매칭 후보로 쓴다.
    housing_columns = get_table_columns("공동주택_전국")
    housing_name_columns = [
        column
        for column in (
            "단지명",
            "단지명_공시가격",
            "단지명_건축물대장",
            "단지명_도로명주소",
        )
        if column in housing_columns
    ]

    def normalize_name_sql(expression: str) -> str:
        return (
            "lower(regexp_replace(coalesce("
            f"{expression}, ''), '[^0-9A-Za-z가-힣]', '', 'g'))"
        )

    housing_address_key = """
        trim(regexp_replace(
            trim(regexp_replace(주소, '\\s+', ' ', 'g')),
            '\\s+(산\\s+)?([0-9]+(-[0-9]+)?|[가-힣]-)$',
            ''
        ))
    """
    name_candidate_queries = []
    for column in housing_name_columns:
        alias_name = (
            f"regexp_extract({column}, '\\(([^)]*)\\)', 1) || "
            f"regexp_extract({column}, '([0-9]+\\s*단지)', 1)"
        )
        name_candidate_queries.append(
            f"""
            SELECT
                {housing_address_key} AS 시군구_주소,
                {normalize_name_sql(column)} AS 단지명_key,
                세대수
            FROM 공동주택_전국
            WHERE 단지구분코드 = '1'
            """
        )
        name_candidate_queries.append(
            f"""
            SELECT
                {housing_address_key} AS 시군구_주소,
                {normalize_name_sql(alias_name)} AS 단지명_key,
                세대수
            FROM 공동주택_전국
            WHERE 단지구분코드 = '1'
              AND regexp_matches(coalesce({column}, ''), '\\([^)]*\\)')
              AND regexp_matches(coalesce({column}, ''), '[0-9]+\\s*단지')
            """
        )
    if "단지명" in housing_name_columns:
        name_candidate_queries.append(
            f"""
            SELECT
                {housing_address_key} AS 시군구_주소,
                {normalize_name_sql("split_part(단지명, ' ', 1)")} AS 단지명_key,
                세대수
            FROM 공동주택_전국
            WHERE 단지구분코드 = '1'
            """
        )
    housing_name_candidates_sql = "\nUNION ALL\n".join(name_candidate_queries)

    # 전처리 CTE 생성
    preprocessing_cte = build_preprocessing_cte(table)

    # 필터 WHERE절 생성
    where_clause, params = build_where_clause(
        시도=시도,
        시군구=시군구,
        읍면동=읍면동,
        연도_시작=연도_시작,
        연도_끝=연도_끝,
        면적대=면적대,
        평형대=평형대,
        전월세구분=전월세구분,
    )

    # 세대수 필터 (파라미터화로 SQL 인젝션 방어)
    세대수_where = ""
    if 세대수_범위:
        세대수_where = "AND (세대수 IS NULL OR (세대수 >= ? AND 세대수 <= ?))"
        params.extend([int(세대수_범위[0]), int(세대수_범위[1])])

    query = f"""
    WITH {preprocessing_cte},

    -- 공백을 정리한 주소당 좌표 한 쌍만 사용해 조인으로 인한 거래량 증가 방지
    coordinate_lookup AS (
        SELECT
            trim(regexp_replace(도로명주소, '\\s+', ' ', 'g')) AS 주소_key,
            경도, 위도
        FROM 좌표
        WHERE 경도 IS NOT NULL AND 위도 IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY trim(regexp_replace(도로명주소, '\\s+', ' ', 'g'))
            ORDER BY 경도, 위도
        ) = 1
    ),

    -- 필터된 데이터
    filtered AS (
        SELECT * FROM preprocessed
        {where_clause}
    ),

    -- 거래량 집계 (단지 + 전용면적_구분 + 연도별)
    aggregated AS (
        SELECT
            시도,
            시군구_parsed AS 시군구,
            읍면동,
            시군구_원본,
            단지명,
            건축년도,
            연식_구분,
            전용면적_구분,
            계약연도,
            도로명,
            도로명주소_key,
            COUNT(*) AS 거래량
        FROM filtered
        GROUP BY ALL
    ),

    -- 좌표 조인 (시도+시군구+도로명 키 매칭)
    joined AS (
        SELECT
            a.*,
            z.경도,
            z.위도
        FROM aggregated a
        LEFT JOIN coordinate_lookup z
            ON trim(regexp_replace(a.도로명주소_key, '\\s+', ' ', 'g')) = z.주소_key
    ),

    -- 세대수 조회 (단지별 1:1 매칭 보장)
    -- 주소 공백과 지번을 정리하고 출처별 단지명을 정확 매칭 후보로 사용
    -- 괄호 속 브랜드명과 N단지 순서가 바뀐 이름도 동일한 키로 정규화
    세대수_이름후보 AS (
        {housing_name_candidates_sql}
    ),
    세대수_lookup AS (
        SELECT
            시군구_주소,
            단지명_key,
            MAX(세대수) AS 세대수
        FROM 세대수_이름후보
        WHERE 단지명_key != ''
        GROUP BY 시군구_주소, 단지명_key
    ),

    -- 읍면동 보정: 시군구 컬럼에 읍면동이 누락된 레코드를
    -- 같은 시도+시군구+단지명에서 가장 빈번한 읍면동으로 채움
    best_emd AS (
        SELECT
            {source["sido"]} AS 시도,
            {source["sigungu"]} AS 시군구,
            단지명,
            mode({source["eupmyeondong"]}) AS best_읍면동
        FROM {table}
        WHERE 시군구 IS NOT NULL
          AND {source["eupmyeondong"]} IS NOT NULL
          AND {source["eupmyeondong"]} != ''
        GROUP BY ALL
    ),

    -- 좌표 보정: 가장 구체적인 도로명(번지 있는)의 좌표를 조회
    -- 시도+시군구+읍면동+단지명으로 GROUP BY하여 동명 단지를 구분
    best_coords AS (
        SELECT
            {source["sido"]} AS 시도,
            {source["sigungu"]} AS 시군구,
            {source["eupmyeondong"]} AS 읍면동,
            단지명,
            FIRST(z.경도 ORDER BY length(z.주소_key) DESC, z.주소_key, z.경도, z.위도) AS best_경도,
            FIRST(z.위도 ORDER BY length(z.주소_key) DESC, z.주소_key, z.경도, z.위도) AS best_위도
        FROM {table} t
        LEFT JOIN coordinate_lookup z
            ON z.주소_key = trim(regexp_replace({source["road_address_key"]}, '\\s+', ' ', 'g'))
        WHERE z.경도 IS NOT NULL
          AND regexp_matches(t.도로명, '\\S')
          AND {source["eupmyeondong"]} != ''
        GROUP BY ALL
    )

    SELECT
        j.시도,
        j.시군구,
        COALESCE(NULLIF(j.읍면동, ''), e.best_읍면동) AS 읍면동,
        j.단지명,
        j.건축년도,
        j.연식_구분,
        j.전용면적_구분,
        j.계약연도,
        j.거래량,
        s.세대수,
        CASE
            WHEN s.세대수 IS NOT NULL AND s.세대수 > 0
            THEN ROUND(j.거래량 * 100.0 / s.세대수, 2)
            ELSE NULL
        END AS 회전율,
        COALESCE(b.best_경도, j.경도) AS 경도,
        COALESCE(b.best_위도, j.위도) AS 위도
    FROM joined j
    -- 1) 읍면동 보정
    LEFT JOIN best_emd e
        ON j.시도 = e.시도
        AND j.시군구 = e.시군구
        AND j.단지명 = e.단지명
    -- 2) 좌표 보정 (보정된 읍면동으로 매칭)
    LEFT JOIN best_coords b
        ON j.시도 = b.시도
        AND j.시군구 = b.시군구
        AND COALESCE(NULLIF(j.읍면동, ''), e.best_읍면동) = b.읍면동
        AND j.단지명 = b.단지명
    -- 3) 세대수 매칭 (세종은 표시용 '세종시'를 제외한 원자료 주소 키 사용)
    LEFT JOIN 세대수_lookup s
        ON s.시군구_주소 = trim(regexp_replace(concat_ws(
            ' ',
            NULLIF(trim(j.시도), ''),
            CASE
                WHEN j.시도 = '세종특별자치시' THEN NULL
                ELSE NULLIF(trim(j.시군구), '')
            END,
            NULLIF(trim(COALESCE(NULLIF(j.읍면동, ''), e.best_읍면동)), '')
        ), '\\s+', ' ', 'g'))
        AND s.단지명_key = {normalize_name_sql("j.단지명")}
    WHERE COALESCE(b.best_경도, j.경도) IS NOT NULL
      AND COALESCE(b.best_위도, j.위도) IS NOT NULL
    {세대수_where}
    ORDER BY 거래량 DESC
    """

    return execute_query(query, params if params else None)
