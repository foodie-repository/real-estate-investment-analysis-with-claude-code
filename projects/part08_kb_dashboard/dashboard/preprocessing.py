"""
KB 데이터 전처리 모듈

전년동월대비 증감률 계산, 전세가율 조회, 거래량 집계, 시계열 데이터 조회를 담당한다.
"""
import pandas as pd

from projects.part08_kb_dashboard.dashboard.db import execute_query, relation_exists


def _source_table_for_yoy(table: str) -> str:
    """사전 계산 YoY 테이블명에서 원본 KB 지수 테이블명을 추정한다."""
    return table.removesuffix("_YoY")


def _raw_yoy_level_filter(level: str, placeholders: str | None = None) -> str:
    """원본 KB 지수에서 시군구/시도 레벨을 고르는 조건을 만든다."""
    if level == "시도":
        filter_sql = "RIGHT(지역코드, 8) = '00000000'"
        if placeholders is not None:
            filter_sql += f"\n                  AND 지역명 IN ({placeholders})"
        return filter_sql

    filter_sql = "RIGHT(지역코드, 8) != '00000000'"
    if placeholders is not None:
        filter_sql += f"\n                  AND LEFT(지역코드, 5) IN ({placeholders})"
    return filter_sql


def _raw_yoy_monthly_cte(
    source_table: str,
    value_col: str,
    level: str,
    placeholders: str | None = None,
) -> str:
    """원본 KB 지수에서 YoY 계산에 필요한 월별 원천 데이터를 추린다."""
    level_filter = _raw_yoy_level_filter(level, placeholders)
    return f"""
            WITH monthly AS (
                SELECT
                    날짜,
                    지역코드,
                    지역명,
                    CAST({value_col} AS DOUBLE) AS value
                FROM {source_table}
                WHERE 매물종별구분 = '아파트'
                  AND 월간주간구분 = '월간'
                  AND LENGTH(지역코드) = 10
                  AND {level_filter}
            )
    """


def _raw_yoy_timeseries_query(
    source_table: str,
    value_col: str,
    level: str,
    placeholders: str,
) -> str:
    """원본 KB 지수 테이블만 있을 때 시계열 YoY를 계산하는 쿼리."""
    monthly_cte = _raw_yoy_monthly_cte(source_table, value_col, level, placeholders)
    sig_cd_expr = "''" if level == "시도" else "LEFT(c.지역코드, 5)"
    order_expr = "c.지역명" if level == "시도" else "sig_cd"
    return f"""
            {monthly_cte}
            SELECT
                c.날짜,
                {sig_cd_expr} AS sig_cd,
                c.지역명,
                ROUND((c.value - p.value) / p.value * 100, 1) AS 값
            FROM monthly c
            JOIN monthly p
              ON c.지역코드 = p.지역코드
             AND c.날짜 = p.날짜 + INTERVAL 1 YEAR
            WHERE p.value > 0
              AND EXTRACT(YEAR FROM c.날짜) BETWEEN ? AND ?
            ORDER BY c.날짜, {order_expr}
            """


def get_yoy_data(table: str, value_col: str, year: int, month: int) -> pd.DataFrame:
    """
    KB 지수 테이블에서 전년동월대비 증감률을 계산한다.

    Args:
        table: KB 테이블명 (예: "KB_매매가격지수")
        value_col: 지수값 컬럼명 (예: "가격지수")
        year: 기준 연도
        month: 기준 월

    Returns:
        DataFrame(sig_cd, 지역명, 증감률)
    """
    query = f"""
    WITH current_month AS (
        SELECT 지역코드, 지역명, CAST({value_col} AS DOUBLE) AS current_val
        FROM {table}
        WHERE 날짜 = ?
          AND 매물종별구분 = '아파트'
          AND 월간주간구분 = '월간'
          AND LENGTH(지역코드) = 10
          AND RIGHT(지역코드, 8) != '00000000'
    ),
    prev_year AS (
        SELECT 지역코드, CAST({value_col} AS DOUBLE) AS prev_val
        FROM {table}
        WHERE 날짜 = ?
          AND 매물종별구분 = '아파트'
          AND 월간주간구분 = '월간'
          AND LENGTH(지역코드) = 10
          AND RIGHT(지역코드, 8) != '00000000'
    )
    SELECT
        LEFT(c.지역코드, 5) AS sig_cd,
        c.지역명,
        ROUND((c.current_val - p.prev_val) / p.prev_val * 100, 1) AS 증감률
    FROM current_month c
    JOIN prev_year p ON c.지역코드 = p.지역코드
    WHERE p.prev_val > 0
    """
    current_date = f"{year}-{month:02d}-01"
    prev_date = f"{year - 1}-{month:02d}-01"
    return execute_query(query, [current_date, prev_date])


def get_jeonse_rate(year: int, month: int) -> pd.DataFrame:
    """
    KB 전세가율을 조회한다.

    Returns:
        DataFrame(sig_cd, 지역명, 전세가율)
    """
    query = """
    SELECT
        LEFT(지역코드, 5) AS sig_cd,
        지역명,
        CAST(전세가격비율 AS DOUBLE) AS 전세가율
    FROM KB_전세가율
    WHERE 날짜 = ?
      AND 매물종별구분 = '아파트'
      AND LENGTH(지역코드) = 10
      AND RIGHT(지역코드, 8) != '00000000'
    """
    target_date = f"{year}-{month:02d}-01"
    return execute_query(query, [target_date])


def get_trade_volume(year: int, month: int) -> pd.DataFrame:
    """
    매매 거래량을 시군구별로 집계한다.
    직거래와 취소 거래는 제외한다.

    Returns:
        DataFrame(sig_kor_nm, 거래량)
    """
    query = """
    SELECT
        CASE
            WHEN 시도 = '세종특별자치시' THEN '세종특별자치시'
            ELSE 시군구
        END AS sig_kor_nm,
        COUNT(*) AS 거래량
    FROM 매매
    WHERE 계약년월 = ?
      AND 거래유형 != '직거래'
      AND (해제사유발생일 IS NULL OR 해제사유발생일 IN ('None', '-', ''))
    GROUP BY sig_kor_nm
    """
    return execute_query(query, [year * 100 + month])


def get_yoy_map_data(
    ts_table: str,
    year: int,
    month: int,
    source_table: str | None = None,
    value_col: str = "가격지수",
) -> pd.DataFrame:
    """
    시군구별 YoY 증감률을 조회한다.

    외장 분석 DB처럼 사전 계산된 YoY 뷰가 있으면 그것을 사용하고,
    독자 실습 DB처럼 원본 KB 지수 테이블만 있으면 즉석에서 계산한다.

    Returns:
        DataFrame(sig_cd, 지역명, 증감률)
    """
    if not relation_exists(ts_table):
        return get_yoy_data(source_table or _source_table_for_yoy(ts_table), value_col, year, month)

    query = f"""
    SELECT
        LEFT(지역코드, 5) AS sig_cd,
        지역명,
        ROUND(YoY증감률, 1) AS 증감률
    FROM {ts_table}
    WHERE 날짜 = ?
      AND 레벨 = '시군구'
    """
    target_date = f"{year}-{month:02d}-01"
    return execute_query(query, [target_date])


def get_all_indicators(year: int, month: int) -> dict[str, pd.DataFrame]:
    """4개 지표 데이터를 한 번에 가져온다."""
    from projects.part08_kb_dashboard.dashboard.constants import INDICATORS

    results = {}
    for name, info in INDICATORS.items():
        if info["type"] == "yoy":
            results[name] = get_yoy_map_data(
                info["ts_table"],
                year,
                month,
                source_table=info["table"],
                value_col=info["value_col"],
            )
        elif info["type"] == "direct":
            results[name] = get_jeonse_rate(year, month)
        elif info["type"] == "count":
            results[name] = get_trade_volume(year, month)
    return results


def get_timeseries(
    table: str,
    value_col: str,
    indicator_type: str,
    sig_cds: list[str],
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """
    선택한 시군구들의 시계열 데이터를 조회한다.

    Returns:
        DataFrame(날짜, sig_cd, 지역명, 값)
    """
    placeholders = ", ".join(["?"] * len(sig_cds))

    if indicator_type == "yoy":
        if relation_exists(table):
            query = f"""
            SELECT
                날짜,
                LEFT(지역코드, 5) AS sig_cd,
                지역명,
                ROUND(YoY증감률, 1) AS 값
            FROM {table}
            WHERE 레벨 = '시군구'
              AND LEFT(지역코드, 5) IN ({placeholders})
              AND EXTRACT(YEAR FROM 날짜) BETWEEN ? AND ?
            ORDER BY 날짜, sig_cd
            """
            params = sig_cds + [start_year, end_year]
        else:
            source_table = _source_table_for_yoy(table)
            query = _raw_yoy_timeseries_query(source_table, value_col, "시군구", placeholders)
            params = sig_cds + [start_year, end_year]
    elif indicator_type == "direct":
        # 전세가율: 직접 값
        query = f"""
        SELECT
            날짜,
            LEFT(지역코드, 5) AS sig_cd,
            지역명,
            CAST({value_col} AS DOUBLE) AS 값
        FROM {table}
        WHERE 매물종별구분 = '아파트'
          AND LENGTH(지역코드) = 10
          AND RIGHT(지역코드, 8) != '00000000'
          AND LEFT(지역코드, 5) IN ({placeholders})
          AND EXTRACT(YEAR FROM 날짜) BETWEEN ? AND ?
        ORDER BY 날짜, sig_cd
        """
        params = sig_cds + [start_year, end_year]
    else:
        return pd.DataFrame()

    return execute_query(query, params)


def get_timeseries_sido(
    table: str,
    value_col: str,
    indicator_type: str,
    sido_names: list[str],
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """
    시도 단위 시계열 데이터를 조회한다.
    KB 테이블에서 시도 레벨 레코드(지역코드 끝 8자리가 '00000000')를 사용한다.

    Args:
        sido_names: KB 단축 시도명 목록 (예: ["서울", "경기"])

    Returns:
        DataFrame(날짜, sig_cd, 지역명, 값)
    """
    placeholders = ", ".join(["?"] * len(sido_names))

    if indicator_type == "yoy":
        if relation_exists(table):
            query = f"""
            SELECT
                날짜,
                '' AS sig_cd,
                지역명,
                ROUND(YoY증감률, 1) AS 값
            FROM {table}
            WHERE 레벨 = '시도'
              AND 지역명 IN ({placeholders})
              AND EXTRACT(YEAR FROM 날짜) BETWEEN ? AND ?
            ORDER BY 날짜, 지역명
            """
            params = sido_names + [start_year, end_year]
        else:
            source_table = _source_table_for_yoy(table)
            query = _raw_yoy_timeseries_query(source_table, value_col, "시도", placeholders)
            params = sido_names + [start_year, end_year]
    elif indicator_type == "direct":
        query = f"""
        SELECT
            날짜,
            '' AS sig_cd,
            지역명,
            CAST({value_col} AS DOUBLE) AS 값
        FROM {table}
        WHERE 매물종별구분 = '아파트'
          AND LENGTH(지역코드) = 10
          AND RIGHT(지역코드, 8) = '00000000'
          AND 지역명 IN ({placeholders})
          AND EXTRACT(YEAR FROM 날짜) BETWEEN ? AND ?
        ORDER BY 날짜, 지역명
        """
        params = sido_names + [start_year, end_year]
    else:
        return pd.DataFrame()

    return execute_query(query, params)


def get_date_range(table: str = "KB_매매가격지수") -> tuple[int, int, int, int]:
    """
    KB 테이블의 날짜 범위를 반환한다.

    Returns:
        (시작연도, 시작월, 종료연도, 종료월)
    """
    query = f"""
    SELECT
        EXTRACT(YEAR FROM MIN(날짜))::INT,
        EXTRACT(MONTH FROM MIN(날짜))::INT,
        EXTRACT(YEAR FROM MAX(날짜))::INT,
        EXTRACT(MONTH FROM MAX(날짜))::INT
    FROM {table}
    WHERE 매물종별구분 = '아파트'
      AND LENGTH(지역코드) = 10
      AND RIGHT(지역코드, 8) != '00000000'
    """
    df = execute_query(query)
    row = df.iloc[0]
    return int(row.iloc[0]), int(row.iloc[1]), int(row.iloc[2]), int(row.iloc[3])


def get_ts_date_range() -> tuple[int, int, int, int]:
    """시계열 분석용 날짜 범위."""
    if not relation_exists("KB_매매가격지수_YoY"):
        monthly_cte = _raw_yoy_monthly_cte("KB_매매가격지수", "가격지수", "시군구")
        query = f"""
        {monthly_cte},
        yoy AS (
            SELECT c.날짜
            FROM monthly c
            JOIN monthly p
              ON c.지역코드 = p.지역코드
             AND c.날짜 = p.날짜 + INTERVAL 1 YEAR
            WHERE p.value > 0
        )
        SELECT
            EXTRACT(YEAR FROM MIN(날짜))::INT,
            EXTRACT(MONTH FROM MIN(날짜))::INT,
            EXTRACT(YEAR FROM MAX(날짜))::INT,
            EXTRACT(MONTH FROM MAX(날짜))::INT
        FROM yoy
        """
        df = execute_query(query)
        row = df.iloc[0]
        return int(row.iloc[0]), int(row.iloc[1]), int(row.iloc[2]), int(row.iloc[3])

    query = """
    SELECT
        EXTRACT(YEAR FROM MIN(날짜))::INT,
        EXTRACT(MONTH FROM MIN(날짜))::INT,
        EXTRACT(YEAR FROM MAX(날짜))::INT,
        EXTRACT(MONTH FROM MAX(날짜))::INT
    FROM KB_매매가격지수_YoY
    WHERE 레벨 = '시군구'
    """
    df = execute_query(query)
    row = df.iloc[0]
    return int(row.iloc[0]), int(row.iloc[1]), int(row.iloc[2]), int(row.iloc[3])
