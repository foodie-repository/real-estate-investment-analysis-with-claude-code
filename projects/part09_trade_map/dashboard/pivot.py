"""
피벗테이블 생성 모듈

거래 데이터를 집계하고 좌표/세대수 정보를 조인하여
지도 시각화용 피벗테이블을 생성한다.
"""
import pandas as pd
from src.utils.address import (
    SIDO_SQL,
    SIGUNGU_SQL,
    EUPMYEONDONG_SQL,
    ROAD_ADDRESS_KEY_SQL,
)
from projects.part09_trade_map.dashboard.db import execute_query
from projects.part09_trade_map.dashboard.preprocessing import (
    build_preprocessing_cte, build_where_clause,
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
        LEFT JOIN 좌표 z ON a.도로명주소_key = z.도로명주소
    ),

    -- 세대수 조회 (단지별 1:1 매칭 보장)
    -- 공동주택_전국.단지명의 첫 단어로 정확 매칭
    -- 같은 (주소, 단지명)에 여러 건이면 가장 큰 세대수 사용
    세대수_lookup AS (
        SELECT
            시군구_주소,
            단지명_first,
            세대수
        FROM (
            SELECT
                regexp_replace(주소, '\\s+[\\d][\\d-]*$', '') AS 시군구_주소,
                split_part(단지명, ' ', 1) AS 단지명_first,
                세대수,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        regexp_replace(주소, '\\s+[\\d][\\d-]*$', ''),
                        split_part(단지명, ' ', 1)
                    ORDER BY 세대수 DESC
                ) AS rn
            FROM 공동주택_전국
            WHERE 단지구분코드 = '1'
        ) sub
        WHERE rn = 1
    ),

    -- 읍면동 보정: 시군구 컬럼에 읍면동이 누락된 레코드를
    -- 같은 시도+시군구+단지명에서 가장 빈번한 읍면동으로 채움
    best_emd AS (
        SELECT
            {SIDO_SQL} AS 시도,
            {SIGUNGU_SQL} AS 시군구,
            단지명,
            mode({EUPMYEONDONG_SQL}) AS best_읍면동
        FROM {table}
        WHERE 시군구 IS NOT NULL
          AND {EUPMYEONDONG_SQL} IS NOT NULL
          AND {EUPMYEONDONG_SQL} != ''
        GROUP BY ALL
    ),

    -- 좌표 보정: 가장 구체적인 도로명(번지 있는)의 좌표를 조회
    -- 시도+시군구+읍면동+단지명으로 GROUP BY하여 동명 단지를 구분
    best_coords AS (
        SELECT
            {SIDO_SQL} AS 시도,
            {SIGUNGU_SQL} AS 시군구,
            {EUPMYEONDONG_SQL} AS 읍면동,
            {ROAD_ADDRESS_KEY_SQL} AS 도로명주소_key,
            단지명,
            FIRST(z.경도 ORDER BY length(z.도로명주소) DESC) AS best_경도,
            FIRST(z.위도 ORDER BY length(z.도로명주소) DESC) AS best_위도
        FROM {table} t
        LEFT JOIN 좌표 z ON z.도로명주소 = {ROAD_ADDRESS_KEY_SQL}
        WHERE z.경도 IS NOT NULL
          AND {EUPMYEONDONG_SQL} != ''
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
    -- 3) 세대수 매칭 (보정된 읍면동 + 단지명 첫단어 정확 매칭)
    LEFT JOIN 세대수_lookup s
        ON s.시군구_주소 = j.시도 || ' ' || j.시군구 || ' ' || COALESCE(NULLIF(j.읍면동, ''), e.best_읍면동)
        AND s.단지명_first = j.단지명
    WHERE COALESCE(b.best_경도, j.경도) IS NOT NULL
      AND COALESCE(b.best_위도, j.위도) IS NOT NULL
    {세대수_where}
    ORDER BY 거래량 DESC
    """

    return execute_query(query, params if params else None)
