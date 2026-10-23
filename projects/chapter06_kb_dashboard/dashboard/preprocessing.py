"""
KB 데이터 전처리 모듈

전년동월대비 증감률 계산, 전세가율 조회, 거래량 집계, 시계열 데이터 조회를 담당한다.
"""
import pandas as pd

from projects.chapter06_kb_dashboard.dashboard.db import column_exists, execute_query, relation_exists


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
        DataFrame(full_nm, 거래량)
    """
    if column_exists("매매", "시도"):
        full_name_expr = """
        CASE
            WHEN 시도 = '세종특별자치시' THEN '세종특별자치시'
            ELSE 시도 || ' ' || 시군구
        END
        """
    else:
        full_name_expr = """
        CASE
            WHEN SPLIT_PART(TRIM(시군구), ' ', 1) = '세종특별자치시'
                THEN '세종특별자치시'
            WHEN RIGHT(SPLIT_PART(TRIM(시군구), ' ', 2), 1) = '시'
             AND RIGHT(SPLIT_PART(TRIM(시군구), ' ', 3), 1) = '구'
                THEN CONCAT_WS(
                    ' ',
                    SPLIT_PART(TRIM(시군구), ' ', 1),
                    SPLIT_PART(TRIM(시군구), ' ', 2),
                    SPLIT_PART(TRIM(시군구), ' ', 3)
                )
            ELSE CONCAT_WS(
                ' ',
                SPLIT_PART(TRIM(시군구), ' ', 1),
                SPLIT_PART(TRIM(시군구), ' ', 2)
            )
        END
        """

    query = f"""
    SELECT
        {full_name_expr} AS full_nm,
        COUNT(*) AS 거래량
    FROM 매매
    WHERE 계약년월 = ?
      AND 거래유형 != '직거래'
      AND (해제사유발생일 IS NULL OR 해제사유발생일 IN ('None', '-', ''))
    GROUP BY full_nm
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
    from projects.chapter06_kb_dashboard.dashboard.constants import INDICATORS

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

    if not sig_cds:
        return pd.DataFrame()

    if indicator_type == "index":
        query = _index_timeseries_query(table, value_col, "시군구", placeholders)
        params = sig_cds + [start_year, end_year]
    elif indicator_type == "yoy":
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

    if not sido_names:
        return pd.DataFrame()

    if indicator_type == "index":
        query = _index_timeseries_query(table, value_col, "시도", placeholders)
        params = sido_names + [start_year, end_year]
    elif indicator_type == "yoy":
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


def _index_timeseries_query(
    table: str, value_col: str, level: str, placeholders: str,
) -> str:
    """원본 지수 이전 기간만 연속된 전월 대비 증감률로 역산한다."""
    monthly_cte = _raw_yoy_monthly_cte(table, value_col, level, placeholders)
    sig_cd = "''" if level == "시도" else "LEFT(지역코드, 5)"
    rate_table = f"{table}_증감률"
    if not relation_exists(rate_table):
        return f"""
        {monthly_cte}
        SELECT 날짜, {sig_cd} AS sig_cd, 지역명, value AS 값, FALSE AS 복원값
        FROM monthly
        WHERE EXTRACT(YEAR FROM 날짜) BETWEEN ? AND ?
        ORDER BY 날짜, 지역명
        """

    # 첫 원본 지수가 유효할 때만 이전 달 = 현재 지수 / (1 + 현재 월 증감률).
    # 정확히 한 달 전 행이 있을 때만 연결하므로 결측 월을 넘어 복원하지 않는다.
    return f"""
    {monthly_cte.replace('WITH monthly', 'WITH RECURSIVE monthly')},
    rates AS (
        SELECT r.날짜, r.지역코드,
               TRY_CAST(r.가격지수증감률 AS DOUBLE) AS rate
        FROM {rate_table} r
        WHERE r.매물종별구분 = '아파트' AND r.월간주간구분 = '월간'
          AND r.지역코드 IN (SELECT DISTINCT 지역코드 FROM monthly)
    ),
    history AS (
        SELECT 날짜, 지역코드, 지역명, value, FALSE AS 복원값
        FROM (
            SELECT * FROM monthly
            QUALIFY ROW_NUMBER() OVER (PARTITION BY 지역코드 ORDER BY 날짜) = 1
        ) first_month
        WHERE value > 0 AND ISFINITE(value)
        UNION ALL
        SELECT p.날짜, h.지역코드, h.지역명,
               h.value / (1 + r.rate / 100), TRUE
        FROM history h
        JOIN rates r ON r.지역코드 = h.지역코드 AND r.날짜 = h.날짜
        JOIN rates p ON p.지역코드 = h.지역코드
                    AND p.날짜 = h.날짜 - INTERVAL 1 MONTH
        WHERE r.rate > -100 AND ISFINITE(r.rate)
    ),
    combined AS (
        SELECT 날짜, 지역코드, 지역명, value, FALSE AS 복원값 FROM monthly
        UNION ALL
        SELECT * FROM history WHERE 복원값
    )
    SELECT 날짜, {sig_cd} AS sig_cd, 지역명, value AS 값, 복원값
    FROM combined
    WHERE EXTRACT(YEAR FROM 날짜) BETWEEN ? AND ?
    ORDER BY 날짜, 지역명
    """


def rebase_timeseries(
    df: pd.DataFrame, base_date, expected_regions: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """원본 KB 가격지수를 공통 시작월=100으로 환산하고 기준값이 없는 지역을 알린다."""
    parts = []
    excluded = sorted(set(expected_regions or []) - set(df["지역명"]))
    for (_, name), group in df.groupby(["sig_cd", "지역명"], sort=False):
        base = group.loc[group["날짜"] == base_date, "값"]
        if base.empty or not (0 < base.iloc[0] < float("inf")):
            excluded.append(name)
            continue
        group = group.loc[group["날짜"] >= base_date].copy()
        group["값"] = group["값"] / float(base.iloc[0]) * 100
        parts.append(group)
    return (pd.concat(parts, ignore_index=True) if parts else df.iloc[:0].copy()), excluded


def get_date_range(
    table: str = "KB_매매가격지수", include_history: bool = False,
) -> tuple[int, int, int, int]:
    """
    KB 테이블의 날짜 범위를 반환한다.

    Returns:
        (시작연도, 시작월, 종료연도, 종료월)
    """
    source = table
    if include_history:
        source = f"""(SELECT 날짜, 매물종별구분, 지역코드 FROM {table}
                      WHERE 월간주간구분 = '월간')"""
        if relation_exists(f"{table}_증감률"):
            source = f"""(SELECT 날짜, 매물종별구분, 지역코드 FROM {table}
                          WHERE 월간주간구분 = '월간'
                          UNION ALL
                          SELECT 날짜, 매물종별구분, 지역코드 FROM {table}_증감률
                          WHERE 월간주간구분 = '월간')"""
    query = f"""
    SELECT
        EXTRACT(YEAR FROM MIN(날짜))::INT,
        EXTRACT(MONTH FROM MIN(날짜))::INT,
        EXTRACT(YEAR FROM MAX(날짜))::INT,
        EXTRACT(MONTH FROM MAX(날짜))::INT
    FROM {source}
    WHERE 매물종별구분 = '아파트'
      AND LENGTH(지역코드) = 10
      {"" if include_history else "AND RIGHT(지역코드, 8) != '00000000'"}
    """
    df = execute_query(query)
    row = df.iloc[0]
    return int(row.iloc[0]), int(row.iloc[1]), int(row.iloc[2]), int(row.iloc[3])


def _get_yoy_date_range(
    ts_table: str,
    source_table: str,
    value_col: str = "가격지수",
    level: str = "시군구",
) -> tuple[int, int, int, int]:
    """사전 계산 뷰 또는 원본 지수에서 사용할 수 있는 YoY 기간을 반환한다."""
    if not relation_exists(ts_table):
        monthly_cte = _raw_yoy_monthly_cte(source_table, value_col, level)
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
    FROM {ts_table}
    WHERE 레벨 = ?
    """.format(ts_table=ts_table)
    df = execute_query(query, [level])
    row = df.iloc[0]
    return int(row.iloc[0]), int(row.iloc[1]), int(row.iloc[2]), int(row.iloc[3])


def get_ts_date_range(
    table: str = "KB_매매가격지수", level: str = "시군구",
) -> tuple[int, int, int, int]:
    """선택한 가격지표와 지역 수준의 시계열 분석용 날짜 범위."""
    return _get_yoy_date_range(f"{table}_YoY", table, level=level)


def _get_yoy_dates(
    ts_table: str,
    source_table: str,
    value_col: str = "가격지수",
) -> set[int]:
    """사전 계산 뷰 또는 원본 지수에서 실제로 존재하는 YoY 연월을 반환한다."""
    if relation_exists(ts_table):
        query = f"""
        SELECT DISTINCT CAST(STRFTIME(날짜, '%Y%m') AS INTEGER) AS 연월
        FROM {ts_table}
        WHERE 레벨 = '시군구'
          AND 날짜 IS NOT NULL
        """
    else:
        monthly_cte = _raw_yoy_monthly_cte(source_table, value_col, "시군구")
        query = f"""
        {monthly_cte}
        SELECT DISTINCT CAST(STRFTIME(c.날짜, '%Y%m') AS INTEGER) AS 연월
        FROM monthly c
        JOIN monthly p
          ON c.지역코드 = p.지역코드
         AND c.날짜 = p.날짜 + INTERVAL 1 YEAR
        WHERE p.value > 0
        """
    df = execute_query(query)
    return set(df["연월"].dropna().astype(int))


def get_map_dates() -> list[int]:
    """필터 적용 후 4개 지도 지표에 실제로 공통 존재하는 YYYYMM 목록."""
    date_sets = [
        _get_yoy_dates("KB_매매가격지수_YoY", "KB_매매가격지수"),
        _get_yoy_dates("KB_전세가격지수_YoY", "KB_전세가격지수"),
        set(
            execute_query(
                """
                SELECT DISTINCT CAST(STRFTIME(날짜, '%Y%m') AS INTEGER) AS 연월
                FROM KB_전세가율
                WHERE 매물종별구분 = '아파트'
                  AND LENGTH(지역코드) = 10
                  AND RIGHT(지역코드, 8) != '00000000'
                  AND 날짜 IS NOT NULL
                """
            )["연월"].dropna().astype(int)
        ),
        set(
            execute_query(
                """
                SELECT DISTINCT TRY_CAST(계약년월 AS INTEGER) AS 연월
                FROM 매매
                WHERE 거래유형 != '직거래'
                  AND (해제사유발생일 IS NULL OR 해제사유발생일 IN ('None', '-', ''))
                  AND TRY_CAST(계약년월 AS INTEGER) IS NOT NULL
                """
            )["연월"].dropna().astype(int)
        ),
    ]
    common_dates = set.intersection(*date_sets)
    if not common_dates:
        raise ValueError("4개 지도 지표에 공통으로 존재하는 연월이 없습니다.")
    return sorted(common_dates)


def get_map_date_range() -> tuple[int, int, int, int]:
    """호환용으로 실제 공통 연월 목록의 첫 달과 마지막 달을 반환한다."""
    dates = get_map_dates()
    start, end = dates[0], dates[-1]
    return start // 100, start % 100, end // 100, end % 100
