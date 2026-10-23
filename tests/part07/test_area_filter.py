"""평형대에 연결된 전용면적 조건을 가격·고점·화면에 함께 적용한다."""
import duckdb
import pytest
from streamlit.testing.v1 import AppTest
from projects.chapter07_price_gap_table.dashboard.analysis import Query, area_limits, compare, monthly
from tests.part07.test_analysis import db


@pytest.fixture
def mixed_areas(db):
    con=duckdb.connect(str(db))
    for area,month,price in [(99.96,202501,300000),(99.96,202608,60000),
                             (59.99,202608,50000),(110.01,202608,200000)]:
        con.execute("INSERT INTO 매매 VALUES ('서울특별시 강남구 역삼동','같은단지',?,?,?,10,2000,'길 1',NULL,'중개거래')",[area,month,price])
    for area,price in [(99.96,10000),(59.99,30000),(110.01,100000)]:
        con.execute("INSERT INTO 전월세 VALUES ('서울특별시 강남구 역삼동','같은단지',?,202608,?,10,2000,'길 1','전세','신규')",[area,price])
    con.close()
    return db


def target(table):
    return next(r for r in table.to_pylist() if r['주소']=='서울특별시 강남구 길 1')


def test_area_applies_before_medians_and_to_history(mixed_areas):
    q=Query(floor_min=2,area_min=83.9,area_max=85)
    row=target(compare(mixed_areas,q))
    assert (row['매매가격'],row['전세가격'],row['매매건수'],row['전세건수'])==(90000,50000,3,2)
    assert row['갭']==40000 and row['월중앙값고점']==150000 and row['고점대비']==60
    history=monthly(mixed_areas,q,(row['단지키'],)).to_pylist()
    assert history[0]['매매가격']==150000
    assert history[-1]['전세가격']==50000
    wide=target(compare(mixed_areas,Query(floor_min=2)))
    assert wide['매매건수']==4 and wide['월중앙값고점']==200000


def test_discontinuous_bands_and_precise_bounds(mixed_areas):
    q=Query(bands=('20평대','40평대'),area_min=59.9,area_max=110.1)
    assert {r['평형대'] for r in compare(mixed_areas,q).to_pylist()}=={'20평대','40평대'}
    assert area_limits(mixed_areas,Query(bands=('30평대',)))==(84,99.96)
    assert area_limits(mixed_areas,Query(sidos=('경기도',)))==(84,84)
    assert area_limits(mixed_areas,Query(bands=('60평 이상',)))==(None,None)
    row=target(compare(mixed_areas,Query(area_min=99.96,area_max=99.96)))
    assert row['매매건수']==row['전세건수']==1
    assert row['매매가격']==60000


@pytest.mark.parametrize('bounds',[(-1,85),(85,84),(float('nan'),85),(84,float('inf'))])
def test_invalid_area_range(bounds):
    with pytest.raises(ValueError,match='전용면적'):
        Query(area_min=bounds[0],area_max=bounds[1])


def test_linked_slider_changes_prices_and_restores_on_band_change(mixed_areas,monkeypatch):
    monkeypatch.setenv('GAP_DB_PATH',str(mixed_areas))
    app=AppTest.from_file('projects/chapter07_price_gap_table/dashboard/app.py',default_timeout=30).run()
    assert not app.exception
    assert app.slider(key='area_range').label=='전용면적 (㎡)'
    assert app.slider(key='area_range').value==(84.,100.)
    app.select_slider(key='period').set_value((202606,202608))
    app.checkbox(key='floor_enabled').check()
    app.slider(key='area_range').set_value((84.,85.)).run()
    assert not app.exception
    row=app.dataframe[0].value.iloc[0]
    assert (row['매매 (억원)'],row['신규 전세 (억원)'],row['전고점 (억원)'])==(9.,5.,15.)
    assert row['매매 건수']==3 and row['전세 건수']==2
    assert len(app.get('plotly_chart'))==2
    app.select_slider(key='period').set_value((202608,202608)).run()
    assert app.slider(key='area_range').value==(84.,85.)
    app.multiselect(key='bands').set_value(['20평대']).run()
    assert not app.exception and app.slider(key='area_range').value==(59.9,60.)
    app.multiselect(key='bands').set_value(['30평대']).run()
    assert not app.exception and app.slider(key='area_range').value==(84.,100.)
    app.multiselect(key='bands').set_value(['20평대','40평대']).run()
    assert not app.exception and app.slider(key='area_range').value==(59.9,110.1)
    assert set(app.dataframe[0].value['평형대'])=={'20평대','40평대'}


def test_region_bounds_empty_band_and_single_area(mixed_areas,monkeypatch):
    monkeypatch.setenv('GAP_DB_PATH',str(mixed_areas))
    app=AppTest.from_file('projects/chapter07_price_gap_table/dashboard/app.py',default_timeout=30).run()
    app.slider(key='area_range').set_value((90.,95.)).run()
    app.multiselect(key='sidos').set_value(['경기도']).run()
    assert not app.exception and app.slider(key='area_range').value==(84.,84.1)
    app.multiselect(key='sidos').set_value(['서울특별시','경기도']).run()
    assert app.slider(key='area_range').value==(84.,100.)
    app.multiselect(key='bands').set_value(['60평 이상']).run()
    assert not app.exception and not any(s.key=='area_range' for s in app.slider)
    assert any('면적 자료가 없습니다' in c.value for c in app.caption)
    app.multiselect(key='bands').set_value([]).run()
    assert not app.exception and any('평형대를' in c.value for c in app.info)
    app.multiselect(key='bands').set_value(['30평대']).run()
    assert not app.exception and app.slider(key='area_range').value==(84.,100.)
