"""
Part06 KB 대시보드 전처리 테스트

독자 환경에서는 사전 계산된 KB_*_YoY 뷰가 없고,
Part04 수집기로 만든 원본 KB 지수 테이블만 있을 수 있다.
"""

import duckdb
import pytest


@pytest.mark.parametrize("level", ["시도", "시군구"])
@pytest.mark.parametrize("broken_rate", [None, "missing", "-100", "nan"])
def test_index_extends_history_using_monthly_rates_without_crossing_gaps(
    tmp_path, monkeypatch, level, broken_rate,
):
    from projects.chapter06_kb_dashboard.dashboard import db, preprocessing

    db_path = tmp_path / "history.duckdb"
    _create_reader_style_kb_db(db_path)
    con = duckdb.connect(str(db_path))
    con.execute("DELETE FROM KB_매매가격지수")
    con.execute("""
        CREATE TABLE KB_매매가격지수_증감률 (
            월간주간구분 VARCHAR, 매물종별구분 VARCHAR,
            지역코드 VARCHAR, 지역명 VARCHAR, 날짜 DATE, 가격지수증감률 VARCHAR
        )
    """)
    for code, name in [("1100000000", "서울"), ("1111000000", "종로구")]:
        con.executemany("INSERT INTO KB_매매가격지수 VALUES ('월간', '아파트', ?, ?, ?, ?)", [
            (code, name, "2025-04-01", 110.),
            (code, name, "2025-05-01", 121.),
        ])
        con.executemany("INSERT INTO KB_매매가격지수_증감률 VALUES ('월간', '아파트', ?, ?, ?, ?)", [
            (code, name, "2024-12-01", "0"),
            (code, name, "2025-01-01", broken_rate),
            (code, name, "2025-02-01", "25"),
            (code, name, "2025-03-01", "-20"),
            (code, name, "2025-04-01", "10"),
            # 원본 지수가 있는 기간에는 증감률에서 계산한 값으로 덮어쓰지 않는다.
            (code, name, "2025-05-01", "99"),
        ])
    con.close()
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))
    params = dict(table="KB_매매가격지수", value_col="가격지수",
                  indicator_type="index", start_year=2024, end_year=2025)
    if level == "시도":
        result = preprocessing.get_timeseries_sido(**params, sido_names=["서울"])
    else:
        result = preprocessing.get_timeseries(**params, sig_cds=["11110"])
    assert result["날짜"].dt.strftime("%Y-%m").tolist() == [
        "2025-01", "2025-02", "2025-03", "2025-04", "2025-05",
    ]
    assert result["값"].tolist() == pytest.approx([100., 125., 100., 110., 121.])
    assert result["복원값"].tolist() == [True, True, True, False, False]
    rebased, excluded = preprocessing.rebase_timeseries(result, result.iloc[1]["날짜"])
    assert rebased["값"].tolist() == pytest.approx([100., 80., 88., 96.8])
    assert excluded == []
    assert preprocessing.get_date_range("KB_매매가격지수", include_history=True) == (2024, 12, 2025, 5)


def _create_reader_style_kb_db(db_path):
    con = duckdb.connect(str(db_path))
    try:
        con.execute("""
            CREATE TABLE KB_매매가격지수 (
                월간주간구분 VARCHAR,
                매물종별구분 VARCHAR,
                지역코드 VARCHAR,
                지역명 VARCHAR,
                날짜 DATE,
                가격지수 DOUBLE
            )
        """)
        con.executemany(
            "INSERT INTO KB_매매가격지수 VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("월간", "아파트", "1100000000", "서울", "2024-01-01", 100.0),
                ("월간", "아파트", "1100000000", "서울", "2025-01-01", 105.0),
                ("월간", "아파트", "1111000000", "종로구", "2024-01-01", 100.0),
                ("월간", "아파트", "1111000000", "종로구", "2025-01-01", 110.0),
            ],
        )
    finally:
        con.close()


@pytest.mark.parametrize("first_value", [0., None])
def test_history_does_not_duplicate_invalid_rows_already_in_raw_index(
    tmp_path, monkeypatch, first_value,
):
    from projects.chapter06_kb_dashboard.dashboard import db, preprocessing
    from projects.chapter06_kb_dashboard.dashboard.charts import create_line_chart

    db_path = tmp_path / "invalid_start.duckdb"
    _create_reader_style_kb_db(db_path)
    con = duckdb.connect(str(db_path))
    con.execute("DELETE FROM KB_매매가격지수")
    con.executemany("INSERT INTO KB_매매가격지수 VALUES ('월간', '아파트', '1100000000', '서울', ?, ?)", [
        ("2025-03-01", first_value), ("2025-04-01", 110.),
    ])
    con.execute("""CREATE TABLE KB_매매가격지수_증감률 AS
                SELECT 월간주간구분, 매물종별구분, 지역코드, 지역명, 날짜,
                       '10' AS 가격지수증감률 FROM KB_매매가격지수""")
    con.close()
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))
    result = preprocessing.get_timeseries_sido(
        "KB_매매가격지수", "가격지수", "index", ["서울"], 2025, 2025,
    )
    assert len(result) == 2
    assert not result["복원값"].any()
    assert len(create_line_chart(result, "가격지수").data) == 1


def test_yoy_map_data_falls_back_to_raw_kb_index(tmp_path, monkeypatch):
    from projects.chapter06_kb_dashboard.dashboard import db, preprocessing

    db_path = tmp_path / "reader.duckdb"
    _create_reader_style_kb_db(db_path)
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))

    df = preprocessing.get_yoy_map_data("KB_매매가격지수_YoY", 2025, 1)

    assert len(df) == 1
    assert df.iloc[0]["sig_cd"] == "11110"
    assert df.iloc[0]["지역명"] == "종로구"
    assert df.iloc[0]["증감률"] == 10.0


def test_yoy_timeseries_and_date_range_fall_back_to_raw_kb_index(tmp_path, monkeypatch):
    from projects.chapter06_kb_dashboard.dashboard import db, preprocessing

    db_path = tmp_path / "reader.duckdb"
    _create_reader_style_kb_db(db_path)
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))

    시군구_df = preprocessing.get_timeseries(
        table="KB_매매가격지수_YoY",
        value_col="가격지수",
        indicator_type="yoy",
        sig_cds=["11110"],
        start_year=2025,
        end_year=2025,
    )
    시도_df = preprocessing.get_timeseries_sido(
        table="KB_매매가격지수_YoY",
        value_col="가격지수",
        indicator_type="yoy",
        sido_names=["서울"],
        start_year=2025,
        end_year=2025,
    )

    assert 시군구_df.iloc[0]["값"] == 10.0
    assert 시도_df.iloc[0]["값"] == 5.0
    assert preprocessing.get_ts_date_range() == (2025, 1, 2025, 1)


def test_yoy_date_range_uses_selected_indicator_and_region_level(tmp_path, monkeypatch):
    from projects.chapter06_kb_dashboard.dashboard import db, preprocessing

    db_path = tmp_path / "yoy_range.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE KB_전세가격지수_YoY (날짜 DATE, 레벨 VARCHAR)")
    con.execute("""INSERT INTO KB_전세가격지수_YoY VALUES
                ('1987-01-01', '시도'), ('2003-01-01', '시군구'),
                ('2026-08-01', '시도'), ('2026-08-01', '시군구')""")
    con.close()
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))
    assert preprocessing.get_ts_date_range("KB_전세가격지수", "시도") == (1987, 1, 2026, 8)
    assert preprocessing.get_ts_date_range("KB_전세가격지수", "시군구") == (2003, 1, 2026, 8)


def test_index_timeseries_uses_raw_prices_for_region_and_sido(tmp_path, monkeypatch):
    from projects.chapter06_kb_dashboard.dashboard import db, preprocessing

    db_path = tmp_path / "index.duckdb"
    _create_reader_style_kb_db(db_path)
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))
    params = dict(table="KB_매매가격지수", value_col="가격지수",
                  indicator_type="index", start_year=2024, end_year=2025)
    region = preprocessing.get_timeseries(**params, sig_cds=["11110"])
    sido = preprocessing.get_timeseries_sido(**params, sido_names=["서울"])
    assert not region.empty
    assert list(region["값"]) == [100., 110.]
    assert list(sido["값"]) == [100., 105.]


def test_rebase_keeps_common_start_and_reports_missing_regions():
    import pandas as pd
    from projects.chapter06_kb_dashboard.dashboard import preprocessing

    df = pd.DataFrame({
        "날짜": pd.to_datetime(["2025-01-01", "2025-03-01", "2025-02-01", "2025-01-01"]),
        "sig_cd": ["1", "1", "2", "3"], "지역명": ["A", "A", "B", "C"],
        "값": [80., 100., 120., 0.],
    })
    rebased, excluded = preprocessing.rebase_timeseries(df, pd.Timestamp("2025-01-01"))
    assert list(rebased["값"]) == [100., 125.]
    assert excluded == ["B", "C"]
    assert list(df["값"]) == [80., 100., 120., 0.]


def test_kb_chart_leaves_missing_months_blank():
    import pandas as pd
    from projects.chapter06_kb_dashboard.dashboard.charts import create_line_chart

    df = pd.DataFrame({
        "날짜": pd.to_datetime(["2025-01-01", "2025-03-01"]),
        "sig_cd": ["1", "1"], "지역명": ["A", "A"], "값": [100., 125.],
    })
    fig = create_line_chart(df, "비교", unit="지수", baseline=100)
    assert len(fig.data[0].y) == 3
    assert pd.isna(fig.data[0].y[1])
    assert fig.data[0].connectgaps is False
    assert fig.layout.shapes[0].y0 == 100


def test_rebase_reports_selected_region_without_any_rows():
    import pandas as pd
    from projects.chapter06_kb_dashboard.dashboard import preprocessing

    df = pd.DataFrame({"날짜": pd.to_datetime(["2025-01-01"]),
                       "sig_cd": ["1"], "지역명": ["A"], "값": [80.]})
    result, excluded = preprocessing.rebase_timeseries(
        df, pd.Timestamp("2025-01-01"), expected_regions=["A", "B"],
    )
    assert result["값"].tolist() == [100.]
    assert excluded == ["B"]


def test_map_date_range_uses_period_common_to_all_four_indicators(tmp_path, monkeypatch):
    from projects.chapter06_kb_dashboard.dashboard import db, preprocessing

    db_path = tmp_path / "map_range.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        for table in ("KB_매매가격지수", "KB_전세가격지수"):
            con.execute(f"""
                CREATE TABLE {table} (
                    월간주간구분 VARCHAR,
                    매물종별구분 VARCHAR,
                    지역코드 VARCHAR,
                    지역명 VARCHAR,
                    날짜 DATE,
                    가격지수 DOUBLE
                )
            """)
            con.executemany(
                f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("월간", "아파트", "1111000000", "종로구", "2024-01-01", 100.0),
                    ("월간", "아파트", "1111000000", "종로구", "2024-02-01", 100.0),
                    ("월간", "아파트", "1111000000", "종로구", "2024-03-01", 100.0),
                    ("월간", "아파트", "1111000000", "종로구", "2025-01-01", 105.0),
                    ("월간", "아파트", "1111000000", "종로구", "2025-02-01", 106.0),
                    ("월간", "아파트", "1111000000", "종로구", "2025-03-01", 107.0),
                ],
            )
        con.execute("""
            CREATE TABLE KB_전세가율 (
                매물종별구분 VARCHAR,
                지역코드 VARCHAR,
                날짜 DATE
            )
        """)
        con.executemany(
            "INSERT INTO KB_전세가율 VALUES (?, ?, ?)",
            [
                ("아파트", "1111000000", "2025-01-01"),
                ("아파트", "1111000000", "2025-03-01"),
            ],
        )
        con.execute("""
            CREATE TABLE 매매 (
                계약년월 INTEGER,
                거래유형 VARCHAR,
                해제사유발생일 VARCHAR
            )
        """)
        con.executemany(
            "INSERT INTO 매매 VALUES (?, '중개거래', NULL)",
            [(202501,), (202502,), (202503,)],
        )
    finally:
        con.close()

    monkeypatch.setattr(db, "_DB_PATH", str(db_path))

    assert preprocessing.get_ts_date_range() == (2025, 1, 2025, 3)
    assert preprocessing.get_map_dates() == [202501, 202503]
    assert preprocessing.get_map_date_range() == (2025, 1, 2025, 3)


def test_trade_volume_keeps_same_named_sigungu_in_different_sido_separate(
    tmp_path, monkeypatch,
):
    from projects.chapter06_kb_dashboard.dashboard import db, preprocessing

    db_path = tmp_path / "trade.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute("""
            CREATE TABLE 매매 (
                시도 VARCHAR,
                시군구 VARCHAR,
                계약년월 INTEGER,
                거래유형 VARCHAR,
                해제사유발생일 VARCHAR
            )
        """)
        con.executemany(
            "INSERT INTO 매매 VALUES (?, ?, ?, ?, ?)",
            [
                ("서울특별시", "강서구", 202501, "중개거래", None),
                ("서울특별시", "강서구", 202501, "중개거래", "-"),
                ("부산광역시", "강서구", 202501, "중개거래", None),
                ("부산광역시", "강서구", 202501, "직거래", None),
            ],
        )
    finally:
        con.close()

    monkeypatch.setattr(db, "_DB_PATH", str(db_path))

    df = preprocessing.get_trade_volume(2025, 1).sort_values("full_nm")

    assert df[["full_nm", "거래량"]].to_dict("records") == [
        {"full_nm": "부산광역시 강서구", "거래량": 1},
        {"full_nm": "서울특별시 강서구", "거래량": 2},
    ]


def test_trade_volume_normalizes_reader_db_full_address_without_sido_column(
    tmp_path, monkeypatch,
):
    from projects.chapter06_kb_dashboard.dashboard import db, preprocessing

    db_path = tmp_path / "reader_trade.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute("""
            CREATE TABLE 매매 (
                시군구 VARCHAR,
                계약년월 INTEGER,
                거래유형 VARCHAR,
                해제사유발생일 VARCHAR
            )
        """)
        con.executemany(
            "INSERT INTO 매매 VALUES (?, ?, ?, ?)",
            [
                ("서울특별시 강서구 염창동", 202501, "중개거래", None),
                ("부산광역시 강서구 명지동", 202501, "중개거래", None),
                ("경기도 수원시 영통구 매탄동", 202501, "중개거래", None),
                ("세종특별자치시 나성동", 202501, "중개거래", None),
            ],
        )
    finally:
        con.close()

    monkeypatch.setattr(db, "_DB_PATH", str(db_path))

    df = preprocessing.get_trade_volume(2025, 1).sort_values("full_nm")

    assert df[["full_nm", "거래량"]].to_dict("records") == [
        {"full_nm": "경기도 수원시 영통구", "거래량": 1},
        {"full_nm": "부산광역시 강서구", "거래량": 1},
        {"full_nm": "서울특별시 강서구", "거래량": 1},
        {"full_nm": "세종특별자치시", "거래량": 1},
    ]


def test_geojson_feature_value_prefers_full_region_name_for_same_named_sigungu():
    from projects.chapter06_kb_dashboard.dashboard.choropleth import _get_feature_value

    value_map = {
        "부산광역시 강서구": 1,
        "서울특별시 강서구": 2,
    }

    assert _get_feature_value(
        value_map,
        {"sig_cd": "11500", "sig_kor_nm": "강서구", "full_nm": "서울특별시 강서구"},
    ) == 2
    assert _get_feature_value(
        value_map,
        {"sig_cd": "26440", "sig_kor_nm": "강서구", "full_nm": "부산광역시 강서구"},
    ) == 1


def test_geojson_feature_value_uses_parent_city_code_for_new_general_gu():
    from projects.chapter06_kb_dashboard.dashboard.choropleth import (
        _get_feature_value,
        get_parent_fallback_names,
    )

    value_map = {"41590": 8.2}
    properties = {
        "sig_cd": "41597",
        "sig_kor_nm": "화성시 동탄구",
        "full_nm": "경기도 화성시 동탄구",
    }

    assert _get_feature_value(value_map, properties) == 8.2
    assert get_parent_fallback_names(
        value_map,
        {"type": "FeatureCollection", "features": [{"properties": properties}]},
    ) == ["경기도 화성시 동탄구"]


def test_sigungu_display_map_keeps_same_names_bound_to_exact_codes():
    from projects.chapter06_kb_dashboard.dashboard.geo import (
        build_sigungu_display_code_map,
    )

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {"properties": {"sig_cd": "11500", "sig_kor_nm": "강서구", "full_nm": "서울특별시 강서구"}},
            {"properties": {"sig_cd": "26440", "sig_kor_nm": "강서구", "full_nm": "부산광역시 강서구"}},
            {"properties": {"sig_cd": "11140", "sig_kor_nm": "중구", "full_nm": "서울특별시 중구"}},
            {"properties": {"sig_cd": "26110", "sig_kor_nm": "중구", "full_nm": "부산광역시 중구"}},
            {"properties": {"sig_cd": "27110", "sig_kor_nm": "중구", "full_nm": "대구광역시 중구"}},
        ],
    }

    display_to_code = build_sigungu_display_code_map(geojson)

    assert display_to_code["강서구 (서울특별시)"] == "11500"
    assert display_to_code["강서구 (부산광역시)"] == "26440"
    assert display_to_code["중구 (서울특별시)"] == "11140"
    assert display_to_code["중구 (부산광역시)"] == "26110"
    assert display_to_code["중구 (대구광역시)"] == "27110"


def test_color_scale_center_is_explicit_for_yoy_and_direct_values():
    import pandas as pd

    from projects.chapter06_kb_dashboard.dashboard.choropleth import (
        get_color_scale_bounds,
    )

    assert get_color_scale_bounds(pd.Series([1.0, 2.0, 3.0]), "yoy") == (-3.0, 3.0, 0.0)
    assert get_color_scale_bounds(pd.Series([-3.0, -2.0, -1.0]), "yoy") == (-3.0, 3.0, 0.0)
    assert get_color_scale_bounds(pd.Series([10.0, 20.0, 100.0]), "direct") == (-60.0, 100.0, 20.0)


def test_trade_volume_color_scale_uses_actual_min_and_max():
    import pandas as pd

    from projects.chapter06_kb_dashboard.dashboard.choropleth import (
        _get_colormap,
        get_color_scale_bounds,
    )

    low, high, center = get_color_scale_bounds(pd.Series([1.0, 30.0, 136.0, 785.0]), "count")
    assert (low, high, center) == (1.0, 785.0, 83.0)

    colormap = _get_colormap(low, high, center=center)
    assert colormap(low).lower().startswith("#2166ac")
    assert colormap(center).lower().startswith("#f7f7f7")
    assert colormap(high).lower().startswith("#b2182b")

    # 모든 값이 같아도 색상 구간이 무너지지 않는다.
    assert get_color_scale_bounds(pd.Series([5.0, 5.0]), "count") == (4.0, 6.0, 5.0)


def test_geojson_feature_value_skips_nan_and_limits_parent_fallback():
    import math

    from projects.chapter06_kb_dashboard.dashboard.choropleth import (
        _get_feature_value,
        get_parent_fallback_names,
    )

    direct_properties = {
        "sig_cd": "11500",
        "sig_kor_nm": "강서구",
        "full_nm": "서울특별시 강서구",
    }
    assert _get_feature_value(
        {"11500": math.nan, "서울특별시 강서구": 2.0},
        direct_properties,
    ) == 2.0

    hwasung_properties = {
        "sig_cd": "41597",
        "sig_kor_nm": "화성시 동탄구",
        "full_nm": "경기도 화성시 동탄구",
    }
    hwasung_values = {"41597": math.nan, "41590": 8.2}
    assert _get_feature_value(hwasung_values, hwasung_properties) == 8.2
    assert get_parent_fallback_names(
        hwasung_values,
        {"type": "FeatureCollection", "features": [{"properties": hwasung_properties}]},
    ) == ["경기도 화성시 동탄구"]

    ordinary_properties = {
        "sig_cd": "41111",
        "sig_kor_nm": "장안구",
        "full_nm": "경기도 수원시 장안구",
    }
    assert _get_feature_value({"41110": 9.9}, ordinary_properties) is None


def test_data_layer_with_no_finite_values_is_gray_and_has_no_nan_label(monkeypatch):
    import math

    import pandas as pd

    from projects.chapter06_kb_dashboard.dashboard.choropleth import (
        create_base_map,
        create_data_layer,
    )

    geojson = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "sig_cd": "11500",
                "sig_kor_nm": "강서구",
                "full_nm": "서울특별시 강서구",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[126.8, 37.5], [126.9, 37.5], [126.9, 37.6], [126.8, 37.5]]],
            },
        }],
    }
    df = pd.DataFrame({"sig_cd": ["11500"], "증감률": [math.nan]})

    monkeypatch.setenv("VWORLD_API_KEY", "test-vworld-key")
    map_object = create_base_map(geojson)
    create_data_layer(
        geojson=geojson,
        df=df,
        value_col="증감률",
        sig_cd_col="sig_cd",
        title="테스트",
        center_mode="yoy",
    ).add_to(map_object)
    html = map_object.get_root().render().lower()

    assert "#cccccc" in html
    assert "nan%" not in html
