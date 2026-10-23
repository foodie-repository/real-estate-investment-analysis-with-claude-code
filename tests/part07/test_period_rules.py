"""거래 구분 정보 제공 전후의 포함 조건과 과거 고점을 검증한다."""
import duckdb
import pytest
from projects.chapter07_price_gap_table.dashboard.analysis import Query, compare, connect, inventory, monthly
from tests.part07.test_analysis import db


@pytest.fixture
def history(db):
    c=duckdb.connect(str(db))
    c.execute('DELETE FROM 매매'); c.execute('DELETE FROM 전월세')
    for month in (201012,201101,202105,202106,202110,202111):
        for kind,price,cancel in [('-',120000,None),('중개거래',80000,None),
                                  ('직거래',900000,None),('중개거래',990000,'20220101')]:
            c.execute("INSERT INTO 매매 VALUES ('서울특별시 강남구 역삼동','같은단지',84,?,?,10,2000,'길 1',?,?)",[month,price,cancel,kind])
        for kind,price in [('-',60000),('신규',40000),('갱신',900000)]:
            c.execute("INSERT INTO 전월세 VALUES ('서울특별시 강남구 역삼동','같은단지',84,?,?,10,2000,'길 1','전세',?)",[month,price,kind])
    c.close()
    return db


@pytest.mark.parametrize('month,sales,rents,sale_price,rent_price',[
    (201101,2,2,100000,50000),(202105,2,2,100000,50000),
    (202106,2,1,100000,40000),(202110,2,1,100000,40000),
    (202111,1,1,80000,40000),
])
def test_period_boundary_keeps_only_eligible_trades(history,month,sales,rents,sale_price,rent_price):
    row=compare(history,Query(start=month,end=month)).to_pylist()[0]
    assert (row['매매건수'],row['전세건수'])==(sales,rents)
    assert (row['매매가격'],row['전세가격'])==(sale_price,rent_price)
    assert row['갭']==sale_price-rent_price


@pytest.mark.parametrize('marker',[None,'','-','None',' NaN ','NULL'])
def test_missing_type_markers_follow_date_boundaries(history,marker):
    c=duckdb.connect(str(history))
    c.execute("UPDATE 매매 SET 거래유형=? WHERE 거래유형='-'",[marker])
    c.execute("UPDATE 전월세 SET 계약구분=? WHERE 계약구분='-'",[marker]);c.close()
    before=compare(history,Query(start=202105,end=202105)).to_pylist()[0]
    after=compare(history,Query(start=202111,end=202111)).to_pylist()[0]
    assert (before['매매건수'],before['전세건수'])==(2,2)
    assert (after['매매건수'],after['전세건수'])==(1,1)


def test_peak_uses_history_but_never_later_transactions(history):
    c=duckdb.connect(str(history))
    c.execute("UPDATE 매매 SET 거래금액=160000 WHERE 계약년월=202105 AND 거래유형='-'")
    c.execute("UPDATE 매매 SET 거래금액=800000 WHERE 계약년월=202111 AND 거래유형='중개거래'")
    c.close()
    row=compare(history,Query(start=202110,end=202110)).to_pylist()[0]
    assert (row['고점년월'],row['월중앙값고점'],row['고점월건수'])==(202105,120000,2)
    assert row['고점조회시작월']==201012
    assert row['고점대비']==pytest.approx(100000/120000*100)
    points=monthly(history,Query(start=202110,end=202110),(row['단지키'],)).to_pylist()
    assert max(p['계약년월'] for p in points)==202110
    assert next(p for p in points if p['계약년월']==202105)['매매가격']==120000
    assert inventory(history)[1]==(201012,202111)


def test_mixed_period_medians_pool_the_eligible_transactions(history):
    row=compare(history,Query(start=202105,end=202111)).to_pylist()[0]
    assert (row['매매건수'],row['전세건수'])==(7,5)
    assert (row['매매가격'],row['전세가격'])==(80000,40000)


def test_historical_streamlit_labels_and_current_labels(history,monkeypatch):
    import json
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('GAP_DB_PATH',str(history))
    app=AppTest.from_file('projects/chapter07_price_gap_table/dashboard/app.py',default_timeout=20).run()
    app.select_slider(key='period').set_value((202105,202105)).run()
    assert not app.exception and app.dataframe
    assert '전세 (억원)' in app.dataframe[0].value.columns
    assert app.number_input(key='min_lease').label=='최소 전세 건수'
    app.selectbox(key='scatter_y').set_value('전세 (억원)').run()
    specs=[json.loads(v.proto.spec) for v in app.get('plotly_chart')]
    assert specs[0]['layout']['yaxis']['title']['text']=='전세 (억원)'
    assert all('신규 전세' not in t['hovertemplate'] for t in specs[0]['data'])
    app.select_slider(key='period').set_value((202111,202111)).run()
    assert not app.exception and '신규 전세 (억원)' in app.dataframe[0].value.columns
    assert app.selectbox(key='scatter_y').value=='신규 전세 (억원)'
    assert app.number_input(key='min_lease').label=='최소 신규 전세 건수'


def test_connections_do_not_share_spill_files(history):
    import gc
    from pathlib import Path
    first=connect(history); second=connect(history)
    paths=[Path(c.execute("SELECT current_setting('temp_directory')").fetchone()[0]) for c in (first,second)]
    try:
        assert paths[0]!=paths[1]
        assert all(path.is_dir() for path in paths)
    finally:
        first.close(); second.close()
    del first,second
    gc.collect()
    assert all(not path.exists() for path in paths)
