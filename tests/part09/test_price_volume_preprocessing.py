import duckdb
import pytest


def _create_price_volume_db(db_path):
    con = duckdb.connect(str(db_path))
    try:
        con.execute("""
            CREATE TABLE 매매 (
                시군구 VARCHAR,
                단지명 VARCHAR,
                전용면적 DOUBLE,
                거래금액 BIGINT,
                계약년월 INTEGER,
                층 INTEGER,
                건축년도 INTEGER,
                도로명 VARCHAR,
                해제사유발생일 VARCHAR,
                거래유형 VARCHAR
            )
        """)
        con.execute("""
            CREATE TABLE 전월세 (
                시군구 VARCHAR,
                단지명 VARCHAR,
                전월세구분 VARCHAR,
                전용면적 DOUBLE,
                보증금 BIGINT,
                계약년월 INTEGER,
                층 INTEGER,
                건축년도 INTEGER,
                도로명 VARCHAR
            )
        """)
        con.executemany(
            "INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("서울특별시 강남구 역삼동", "테스트단지", 84.0, 100000, 202501, 10, 2010, "테스트로 1", None, "중개거래"),
                ("서울특별시 강남구 역삼동", "직거래단지", 84.0, 90000, 202501, 3, 2010, "테스트로 2", None, "직거래"),
                ("서울특별시 강남구 역삼동", "취소단지", 84.0, 80000, 202501, 4, 2010, "테스트로 3", "20250120", "중개거래"),
            ],
        )
        con.executemany(
            "INSERT INTO 전월세 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("서울특별시 강남구 역삼동", "테스트단지", "전세", 84.0, 60000, 202501, 5, 2010, "테스트로 1"),
                ("서울특별시 강남구 역삼동", "월세단지", "월세", 84.0, 10000, 202501, 2, 2010, "테스트로 4"),
            ],
        )
    finally:
        con.close()


def test_individual_and_monthly_queries_keep_expected_outputs(tmp_path, monkeypatch):
    from projects.chapter09_price_volume.dashboard import db, preprocessing

    db_path = tmp_path / "price_volume.duckdb"
    _create_price_volume_db(db_path)
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))

    params = dict(
        시도="서울특별시",
        시군구="강남구",
        읍면동=["역삼동"],
        단지=None,
        거래유형="매매+전세",
        평형대=["30평대"],
        시작년월=202501,
        종료년월=202501,
    )

    individual = preprocessing.get_individual_trades(**params)
    monthly = preprocessing.get_monthly_summary(**params)

    assert list(individual.keys()) == ["매매", "전세"]
    assert individual["매매"].iloc[0]["단지명"] == "테스트단지"
    assert individual["매매"].iloc[0]["가격_억"] == 10.0
    assert individual["매매"].iloc[0]["평형대"] == "30평대"
    assert individual["전세"].iloc[0]["가격_억"] == 6.0

    assert monthly["매매"].iloc[0]["중위가_억"] == 10.0
    assert monthly["매매"].iloc[0]["거래량"] == 1
    assert monthly["전세"].iloc[0]["중위가_억"] == 6.0
    assert monthly["전세"].iloc[0]["거래량"] == 1


def test_summary_stats_excludes_direct_and_cancelled_trades(tmp_path, monkeypatch):
    from projects.chapter09_price_volume.dashboard import db, preprocessing

    db_path = tmp_path / "price_volume.duckdb"
    _create_price_volume_db(db_path)
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))

    stats = preprocessing.get_summary_stats(
        시도="서울특별시",
        시군구="강남구",
        읍면동=["역삼동"],
        평형대=["30평대"],
        시작년월=202501,
        종료년월=202501,
    )

    assert stats["총거래건수"] == 1
    assert stats["최고가_억"] == 10.0
    assert stats["최저가_억"] == 10.0
    assert stats["최근거래"].iloc[0]["단지명"] == "테스트단지"


def test_selected_complexes_keep_address_area_and_unrounded_medians(tmp_path, monkeypatch):
    from projects.chapter09_price_volume.dashboard import db, preprocessing

    db_path = tmp_path / "comparison.duckdb"
    _create_price_volume_db(db_path)
    con = duckdb.connect(str(db_path))
    con.executemany(
        "INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("서울특별시 강남구 역삼동", "비교단지", 84., 65000, 202501, 10, 2010, "비교로 1", None, "중개거래"),
            ("서울특별시 강남구 역삼동", "비교단지", 84., 65100, 202501, 11, 2010, "비교로 1", None, "중개거래"),
            ("서울특별시 강남구 역삼동", "비교단지", 59., 40000, 202501, 10, 2010, "비교로 1", None, "중개거래"),
            ("서울특별시 강남구 삼성동", "비교단지", 84., 90000, 202501, 10, 2010, "비교로 2", None, "중개거래"),
        ],
    )
    con.close()
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))
    df = preprocessing.get_monthly_summary(
        시도="서울특별시", 시군구="강남구", 단지=["테스트단지", "비교단지"],
        거래유형="매매만", 시작년월=202501, 종료년월=202501,
    )["매매"]
    assert len(df) == 4
    assert df["비교대상"].nunique() == 4
    assert sorted(df["중위가_억"]) == [4., 6.505, 9., 10.]
    assert sorted(df["거래량"]) == [1, 1, 1, 2]


def _comparison_data():
    import pandas as pd

    return {"매매": pd.DataFrame({
        "계약년월": [202501, 202503, 202501, 202502, 202503],
        "비교대상": ["A", "A", "B", "B", "B"],
        "중위가_억": [10., 12., 5., 6., 6.5],
        "거래량": [2, 3, 1, 2, 3],
    })}


def test_line_chart_bridges_only_missing_intervals_with_dots():
    import pandas as pd
    from projects.chapter09_price_volume.dashboard.charts import create_line_chart

    fig = create_line_chart(_comparison_data())
    lines = [trace for trace in fig.data if trace.type == "scatter" and trace.line.dash != "dot"]
    assert len(lines) == 2
    first = next(trace for trace in lines if trace.legendgroup == "A")
    assert list(first.x) == ["2025-01", "2025-02", "2025-03"]
    assert first.y[0] == 10.
    assert pd.isna(first.y[1])
    assert first.y[2] == 12.
    assert first.connectgaps is False
    bars = [trace for trace in fig.data if trace.type == "bar"]
    assert list(next(trace for trace in bars if trace.legendgroup == "A").y) == [2, 0, 3]
    bridges = [trace for trace in fig.data if trace.type == "scatter" and trace.line.dash == "dot"]
    assert len(bridges) == 1
    assert bridges[0].legendgroup == "A"
    assert list(bridges[0].x) == ["2025-01", "2025-03", None]
    assert list(bridges[0].y) == [10., 12., None]
    assert bridges[0].hoverinfo == "skip"
    assert bridges[0].showlegend is False
    assert fig.layout.yaxis2.tickformat == ",d"
    assert fig.layout.yaxis2.dtick >= 1


def test_rebased_chart_uses_same_month_and_preserves_volume():
    from projects.chapter09_price_volume.dashboard.charts import create_line_chart

    fig = create_line_chart(_comparison_data(), base_month=202501)
    lines = {trace.legendgroup: trace for trace in fig.data if trace.type == "scatter" and trace.line.dash != "dot"}
    assert list(lines["B"].y) == [100., 120., 130.]
    assert lines["A"].y[0] == 100.
    assert lines["A"].y[2] == 120.
    assert "100" in fig.layout.annotations[0].text
    assert any(shape.y0 == 100 and shape.y1 == 100 for shape in fig.layout.shapes)


def test_missing_or_zero_base_is_reported_not_rebased_to_another_month():
    from projects.chapter09_price_volume.dashboard import preprocessing

    data = _comparison_data()
    df, excluded = preprocessing.prepare_monthly_comparison(data, base_month=202502)
    assert excluded == ["매매 · A"]
    assert set(df["매매"]["비교대상"]) == {"B"}
    assert df["매매"]["표시값"].iloc[0] == 100.
    data["매매"].loc[data["매매"]["계약년월"] == 202501, "중위가_억"] = 0.
    df, excluded = preprocessing.prepare_monthly_comparison(data, base_month=202501)
    assert df["매매"].empty
    assert len(excluded) == 2


def test_common_base_months_require_all_trade_types_and_series():
    from projects.chapter09_price_volume.dashboard import preprocessing

    data = _comparison_data()
    assert preprocessing.get_common_base_months(data) == [202501, 202503]
    data["전세"] = data["매매"].query("계약년월 == 202503").copy()
    assert preprocessing.get_common_base_months(data) == [202503]


@pytest.mark.parametrize("external", [False, True])
def test_parcel_keeps_historical_road_variants_in_one_complex(tmp_path, monkeypatch, external):
    from projects.chapter09_price_volume.dashboard import db, preprocessing

    path = tmp_path / "parcels.duckdb"
    _create_price_volume_db(path)
    con = duckdb.connect(str(path))
    for table in ("매매", "전월세"):
        con.execute(f"ALTER TABLE {table} ADD COLUMN 지번 VARCHAR DEFAULT '123'")
    con.execute("""
        INSERT INTO 매매 VALUES
        ('서울특별시 강남구 역삼동', '테스트단지', 84, 120000, 202502, 10, 2010,
         '테스트로', NULL, '중개거래', '123'),
        ('서울특별시 강남구 역삼동', '테스트단지', 84, 70000, 202502, 10, 2010,
         '테스트로 2', NULL, '중개거래', '456')
    """)
    if external:
        for table, amount, source_amount in (("매매", "거래금액", "거래금액(만원)"), ("전월세", "보증금", "보증금(만원)")):
            con.execute(f'ALTER TABLE {table} RENAME COLUMN 전용면적 TO "전용면적(㎡)"')
            con.execute(f'ALTER TABLE {table} ALTER COLUMN {amount} TYPE VARCHAR')
            con.execute(f'ALTER TABLE {table} RENAME COLUMN {amount} TO "{source_amount}"')
            con.execute(f"ALTER TABLE {table} RENAME COLUMN 지번 TO 번지")
            con.execute(f"ALTER TABLE {table} ADD COLUMN 시도 VARCHAR DEFAULT '서울특별시'")
            con.execute(f"ALTER TABLE {table} ADD COLUMN 읍면동 VARCHAR DEFAULT '역삼동'")
            con.execute(f"UPDATE {table} SET 시군구 = '강남구'")
    con.close()
    monkeypatch.setattr(db, "_DB_PATH", str(path))
    data = preprocessing.get_monthly_summary(
        시도="서울특별시", 시군구="강남구", 단지=["테스트단지"], 거래유형="매매만",
    )["매매"]
    jan_label = data.loc[data["계약년월"] == 202501, "비교대상"].iloc[0]
    same_complex = data[data["비교대상"] == jan_label]
    assert list(same_complex["중위가_억"]) == [10., 12.]
    assert data["비교대상"].nunique() == 2


def test_multi_region_identity_and_area_filters_match_all_outputs(tmp_path, monkeypatch):
    from projects.chapter09_price_volume.dashboard import db, preprocessing as p

    path = tmp_path / 'multi.duckdb'
    _create_price_volume_db(path)
    con = duckdb.connect(str(path))
    # 같은 구·동·단지명이 다른 시도에도 있는 경우를 포함한다.
    rows = [
        ('서울특별시 중구 중앙동', '같은단지', 84., 100000),
        ('부산광역시 중구 중앙동', '같은단지', 85., 60000),
        ('서울특별시 중구 중앙동', '다른단지', 84., 40000),
        ('부산광역시 중구 중앙동', '다른단지', 84., 50000),
        ('부산광역시 중구 중앙동', '같은단지', 90., 70000),
        ('부산광역시 중구 중앙동', '같은단지', 59., 30000),
    ]
    for address, name, area, price in rows:
        con.execute("INSERT INTO 매매 VALUES (?, ?, ?, ?, 202501, 10, 2010, '중앙로 1', NULL, '중개거래')", [address,name,area,price])
        con.execute("INSERT INTO 전월세 VALUES (?, ?, '전세', ?, ?, 202501, 10, 2010, '중앙로 1')", [address,name,area,price/2])
    con.close()
    monkeypatch.setattr(db, '_DB_PATH', str(path))
    params = dict(시도=['서울특별시', '부산광역시'],
                  시군구=[('서울특별시', '중구'), ('부산광역시', '중구')],
                  읍면동=[('서울특별시', '중구', '중앙동'), ('부산광역시', '중구', '중앙동')],
                  단지=[('서울특별시', '중구', '중앙동', '같은단지'),
                        ('부산광역시', '중구', '중앙동', '다른단지')],
                  평형대=['30평대'])
    assert p.get_area_range(**params) == (84.,84.)
    params['단지'][1] = ('부산광역시', '중구', '중앙동', '같은단지')
    assert p.get_area_range(**params) == (84.,90.)
    assert p.get_area_range(**{**params, '평형대':['20평대','30평대']}) == (59.,90.)
    params['전용면적']=(84.,85.)
    individual = p.get_individual_trades(**params)
    monthly = p.get_monthly_summary(**params)
    stats = p.get_summary_stats(**params)
    assert sorted(individual['매매']['전용면적']) == [84.,85.]
    assert sorted(individual['전세']['전용면적']) == [84.,85.]
    assert sorted(monthly['매매']['중위가_억']) == [6.,10.]
    assert sorted(monthly['전세']['중위가_억']) == [3.,5.]
    assert monthly['매매']['거래량'].sum() == stats['총거래건수'] == 2
    assert sorted(stats['최근거래']['전용면적']) == [84.,85.]
    # 선택한 상위 지역 밖에 남은 동명 하위 지역은 포함하지 않는다.
    selected = p.get_individual_trades(**{**params, '시군구':[('서울특별시','중구')]})
    assert selected['매매']['가격_억'].tolist() == [10.]


def test_dotted_bridges_do_not_extrapolate_or_create_missing_prices():
    import pandas as pd
    from projects.chapter09_price_volume.dashboard.charts import create_line_chart, create_scatter_chart

    data = {'매매':pd.DataFrame({
        '계약년월':[202501,202504,202502,202503],
        '비교대상':['A','A','B','B'],
        '중위가_억':[10.,13.,5.,6.], '거래량':[1,1,1,1],
    })}
    fig = create_line_chart(data, base_month=None)
    dotted = [t for t in fig.data if t.type=='scatter' and t.line.dash=='dot']
    assert len(dotted)==1
    assert list(dotted[0].x)==['2025-01','2025-04',None]
    assert list(dotted[0].y)==[10.,13.,None]
    assert len(data['매매'])==4
    scatter = create_scatter_chart({'전세':pd.DataFrame({
        '계약년월':[202501], '단지명':['A'], '전용면적':[84.], '가격_억':[5.],
        '층':[10], '추정평형':[33], '평형대':['30평대'],
    })})
    assert scatter.layout.yaxis2.dtick==1
    assert scatter.layout.yaxis2.tickformat==',d'


def test_area_slider_resets_when_complex_ranges_do_not_overlap(tmp_path, monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from projects.chapter09_price_volume.dashboard import db

    path = tmp_path / 'area_ui.duckdb'
    _create_price_volume_db(path)
    con = duckdb.connect(str(path))
    con.execute("""INSERT INTO 매매 VALUES
        ('서울특별시 강남구 역삼동', '작은단지', 82.52, 70000, 202502, 10, 2010, '면적로 1', NULL, '중개거래'),
        ('서울특별시 강남구 역삼동', '큰단지', 110.25, 90000, 202502, 10, 2010, '면적로 2', NULL, '중개거래')""")
    con.execute("UPDATE 매매 SET 계약년월 = 202401 WHERE 단지명 = '취소단지'")
    con.close()
    monkeypatch.setattr(db, '_DB_PATH', str(path))
    st.cache_data.clear()
    try:
        at = AppTest.from_file('projects/chapter09_price_volume/dashboard/app.py', default_timeout=20).run()
        assert not at.exception
        key = ('서울특별시','강남구','역삼동')
        at.multiselect(key='region_단지').set_value([(*key,'테스트단지')]).run()
        at.slider(key='area_range').set_value((84.,84.)).run()
        at.multiselect(key='region_단지').set_value([(*key,'작은단지')]).run()
        assert not at.exception
        assert at.slider(key='area_range').value == (82.5,82.6)
        assert at.metric[0].value == '1건'
        at.multiselect(key='region_단지').set_value([(*key,'작은단지'),(*key,'테스트단지')]).run()
        assert at.slider(key='area_range').value == (82.5,84.)
        assert at.metric[0].value == '2건'
        at.multiselect(key='region_단지').set_value([])
        next(w for w in at.multiselect if w.label=='평형대').set_value(['40평대']).run()
        assert not at.exception
        assert at.slider(key='area_range').value == (110.2,110.3)
        assert at.metric[0].value == '1건'
    finally:
        st.cache_data.clear()


def test_ui_keeps_multiple_region_paths_and_removes_only_outside_selections(tmp_path, monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from projects.chapter09_price_volume.dashboard import db

    path = tmp_path / 'regions_ui.duckdb'
    _create_price_volume_db(path)
    con = duckdb.connect(str(path))
    con.execute("""INSERT INTO 매매 VALUES
        ('부산광역시 중구 중앙동', '테스트단지', 84.0, 60000, 202401, 10, 2010, '중앙로 1', NULL, '중개거래')""")
    con.close()
    monkeypatch.setattr(db, '_DB_PATH', str(path))
    st.cache_data.clear()
    try:
        at=AppTest.from_file('projects/chapter09_price_volume/dashboard/app.py', default_timeout=20).run()
        at.multiselect(key='region_시도').set_value(['서울특별시','부산광역시']).run()
        districts=[('서울특별시','강남구'),('부산광역시','중구')]
        dongs=[(*districts[0],'역삼동'),(*districts[1],'중앙동')]
        complexes=[(*dong,'테스트단지') for dong in dongs]
        at.multiselect(key='region_시군구').set_value(districts).run()
        at.multiselect(key='region_읍면동').set_value(dongs).run()
        at.multiselect(key='region_단지').set_value(complexes).run()
        assert not at.exception
        assert at.multiselect(key='region_단지').value==complexes
        assert at.metric[0].value=='2건'
        at.multiselect(key='region_시도').set_value(['부산광역시']).run()
        assert not at.exception
        assert at.multiselect(key='region_시군구').value==[districts[1]]
        assert at.multiselect(key='region_읍면동').value==[dongs[1]]
        assert at.multiselect(key='region_단지').value==[complexes[1]]
        assert at.metric[0].value=='1건'
        assert at.metric[1].value=='6.0억'
    finally:
        st.cache_data.clear()


@pytest.mark.parametrize("complexes,bands,expected", [
    (["비교A"], ["20평대", "30평대"], 2),
    (["비교A", "비교B"], ["30평대"], 2),
    (["비교A", "비교B"], ["20평대", "30평대"], 4),
])
def test_scatter_and_monthly_share_complex_band_legends(tmp_path, monkeypatch, complexes, bands, expected):
    from projects.chapter09_price_volume.dashboard import db, preprocessing as p
    from projects.chapter09_price_volume.dashboard.charts import create_scatter_chart, create_line_chart

    path = tmp_path / "legend.duckdb"
    _create_price_volume_db(path)
    con = duckdb.connect(str(path))
    for name, road in [("비교A", "비교로 1"), ("비교B", "비교로 2")]:
        for area in [59., 84.]:
            con.execute("INSERT INTO 매매 VALUES (?, ?, ?, 100000, 202501, 10, 2010, ?, NULL, '중개거래')",
                        ["서울특별시 강남구 역삼동", name, area, road])
            con.execute("INSERT INTO 전월세 VALUES (?, ?, '전세', ?, 60000, 202501, 10, 2010, ?)",
                        ["서울특별시 강남구 역삼동", name, area, road])
    con.close()
    monkeypatch.setattr(db, "_DB_PATH", str(path))
    params = dict(시도="서울특별시", 시군구="강남구", 단지=complexes, 평형대=bands)
    individual = p.get_individual_trades(**params)
    monthly = p.get_monthly_summary(**params)
    scatter, line = create_scatter_chart(individual), create_line_chart(monthly)
    expected_names = {f"{name} · {band}" for name in complexes for band in bands}
    assert {t.name for t in scatter.data if t.showlegend} == expected_names
    assert len([t for t in scatter.data if t.showlegend]) == expected
    colors = {t.legendgroup: t.line.color for t in line.data if t.showlegend}
    for trace in scatter.data:
        if trace.type == "scatter":
            assert len(trace.x) == 1
            assert trace.name == f"{trace.customdata[0][0]} · {trace.customdata[0][4]}"
            assert trace.marker.color == colors[trace.legendgroup]
        else:
            assert sum(trace.y) == 1
            assert "합계" not in trace.hovertemplate
            assert trace.marker.color == colors[trace.legendgroup]
    assert len(set(colors.values())) == expected
    assert scatter.layout.barmode == line.layout.barmode == "stack"
    assert all("선택 대상 전체" not in a.text for a in scatter.layout.annotations[2:])


def test_scatter_legend_includes_rent_only_and_disambiguates_names():
    import pandas as pd
    from projects.chapter09_price_volume.dashboard.charts import create_scatter_chart, create_line_chart

    def trades(name, address, price, month=202501):
        return dict(계약년월=month, 단지명=name, 전용면적=84., 가격_억=price,
                    층=10, 추정평형=33, 평형대="30평대",
                    비교대상=f"{name} · 30평대 ({address} 도로명 비교로 1)")
    data = {
        "매매": pd.DataFrame([trades("동명단지", "서울특별시 강남구 역삼동", 10.)]),
        "전세": pd.DataFrame([trades("동명단지", "서울특별시 강남구 삼성동", 6.),
                             trades("가전세전용", "서울특별시 강남구 역삼동", 5., 202502)]),
    }
    scatter = create_scatter_chart(data)
    assert {t.name for t in scatter.data if t.showlegend} == {
        "동명단지 · 30평대 (역삼동)", "동명단지 · 30평대 (삼성동)", "가전세전용 · 30평대"}
    monthly = {k: df.rename(columns={"가격_억": "중위가_억"}).assign(거래량=1) for k, df in data.items()}
    line = create_line_chart(monthly)
    index = create_line_chart(monthly, base_month=202501)
    colors = {t.legendgroup: t.marker.color for t in scatter.data if t.showlegend}
    for fig in (line, index):
        for trace in fig.data:
            if trace.showlegend:
                assert trace.line.color == colors[trace.legendgroup]
                assert trace.name in {t.name for t in scatter.data if t.showlegend}
    assert len(index.layout.meta["excluded"]) == 1
