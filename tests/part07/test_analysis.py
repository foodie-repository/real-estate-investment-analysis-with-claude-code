from pathlib import Path
import duckdb
import pytest
from projects.chapter07_price_gap_table.dashboard.analysis import Query, compare, filter_sort, monthly

@pytest.fixture
def db(tmp_path):
    path=tmp_path/'input.duckdb'
    c=duckdb.connect(str(path))
    c.execute('''CREATE TABLE 매매(시군구 VARCHAR, 단지명 VARCHAR, 전용면적 DOUBLE, 계약년월 INTEGER, 거래금액 BIGINT, 층 INTEGER, 건축년도 INTEGER, 도로명 VARCHAR, 해제사유발생일 VARCHAR, 거래유형 VARCHAR)''')
    c.execute('''CREATE TABLE 전월세(시군구 VARCHAR, 단지명 VARCHAR, 전용면적 DOUBLE, 계약년월 INTEGER, 보증금 BIGINT, 층 INTEGER, 건축년도 INTEGER, 도로명 VARCHAR, 전월세구분 VARCHAR, 계약구분 VARCHAR)''')
    sale=[('서울특별시 강남구 역삼동','같은단지',84,ym,price,floor,2000,road,cancel,kind) for ym,price,floor,road,cancel,kind in [
      (202501,100000,10,'길 1','-','중개거래'),(202501,200000,10,'길 1',None,'중개거래'),
      (202606,80000,10,'길 1',None,'중개거래'),(202607,90000,10,'길 1','-','중개거래'),(202608,100000,10,'길 1','-','중개거래'),
      (202608,999999,10,'길 1','20260901','중개거래'),(202608,888888,10,'길 1',None,'직거래'),
      (202608,777777,10,'길 1',None,None),(202608,10000,1,'길 1',None,'중개거래'),
      (202609,900000,10,'길 1',None,'중개거래'),(202608,50000,10,'길 2',None,'중개거래')]]
    sale += [('경기도 광주시 역동','같은단지',84,202608,70000,10,2010,'길 1',None,'중개거래')]
    c.executemany('INSERT INTO 매매 VALUES (?,?,?,?,?,?,?,?,?,?)',sale)
    lease=[('서울특별시 강남구 역삼동','같은단지',84,202608,v,10,2000,'길 1','전세',k) for v,k in [(40000,'신규'),(60000,'신규'),(20000,'갱신'),(10000,None)]]
    lease += [('서울특별시 강남구 역삼동','전세만',84,202608,30000,10,2005,'길 3','전세','신규')]
    c.executemany('INSERT INTO 전월세 VALUES (?,?,?,?,?,?,?,?,?,?)',lease)
    c.close()
    return path

def q(**kw):
    return Query(start=202606,end=202608,floor_min=2,**kw)

def test_medians_filters_peak_and_missing(db):
    rows=compare(db,q()).to_pylist()
    a=next(r for r in rows if r['주소']=='서울특별시 강남구 길 1')
    assert a['매매가격']==90000 and a['전세가격']==50000
    assert a['갭']==40000 and a['전세가율']==pytest.approx(50000/90000*100)
    assert a['매매건수']==3 and a['전세건수']==2
    assert a['월중앙값고점']==150000 and a['고점년월']==202501
    assert a['고점대비']==60
    assert len(rows)==4  # 같은 이름·다른 주소와 다른 시도, 전세만 있는 행 보존
    missing=next(r for r in rows if r['단지명']=='전세만')
    assert missing['갭'] is None and missing['매매가격'] is None
    assert missing['매매건수']==0

def test_location_pairs_and_empty_selection(db):
    assert compare(db,q(regions=('경기도 광주시',))).num_rows==1
    assert compare(db,q(sidos=('인천광역시',))).num_rows==0

def test_numeric_filter_sort_and_null_last(db):
    t=compare(db,q())
    rows=filter_sort(t,sort='매매가격',descending=True).to_pylist()
    assert [r['매매가격'] for r in rows]==[90000,70000,50000,None]
    assert filter_sort(t,gap_min=30000,gap_max=50000,min_sale=2,min_lease=2).num_rows==1

def test_lease_price_filter_boundaries_and_missing(db):
    t=compare(db,q())
    assert filter_sort(t,lease_min=30000,lease_max=50000).num_rows==2
    assert filter_sort(t,lease_min=50000,lease_max=50000).num_rows==1
    assert filter_sort(t,lease_max=29999).num_rows==0
    assert filter_sort(t,sale_min=90000,sale_max=90000,lease_min=50000,lease_max=50000).num_rows==1
    assert filter_sort(t,sale_max=80000,lease_min=50000).num_rows==0
    assert filter_sort(t).num_rows==4  # 가격 조건을 해제하면 한쪽 가격이 없는 행도 보존한다.

def test_price_sliders_filter_and_adjust_to_query(db,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('GAP_DB_PATH',str(db))
    app=AppTest.from_file('projects/chapter07_price_gap_table/dashboard/app.py',default_timeout=20).run()
    app.select_slider(key='period').set_value((202606,202608))
    app.checkbox(key='floor_enabled').check().run()
    app.checkbox(key='price_enabled').check()
    app.checkbox(key='lease_price_enabled').check().run()
    assert not app.exception
    assert app.slider(key='sale_range').label=='매매가격 범위'
    assert app.slider(key='sale_range').value==(5.0,9.0)
    assert app.slider(key='lease_range').value==(3.0,5.0)
    app.slider(key='sale_range').set_value((8.0,9.0))
    app.slider(key='lease_range').set_value((4.0,5.0)).run()
    assert not app.exception and len(app.dataframe[0].value)==1
    app.slider(key='lease_range').set_value((3.0,4.0)).run()
    assert not app.exception and not app.dataframe
    app.checkbox(key='lease_price_enabled').uncheck().run()
    assert len(app.dataframe[0].value)==1
    app.select_slider(key='period').set_value((202501,202501)).run()
    assert not app.exception and app.dataframe
    assert app.slider(key='sale_range').value==(15.0,15.1)
    app.multiselect(key='sidos').set_value(['경기도']).run()
    assert not app.exception and not app.dataframe

def test_floor_filter_applies_to_peak_and_current(db):
    assert compare(db,Query(start=202606,end=202608,floor_max=1)).to_pylist()[0]['매매가격']==10000

def test_monthly_history_has_no_future(db):
    row=next(r for r in compare(db,q()).to_pylist() if r['주소']=='서울특별시 강남구 길 1')
    hist=monthly(db,q(),(row['단지키'],)).to_pylist()
    assert max(r['계약년월'] for r in hist)==202608
    assert hist[0]['매매가격']==150000

def test_external_schema(db,tmp_path):
    ext=tmp_path/'external.duckdb'
    c=duckdb.connect(str(ext))
    c.execute(f"ATTACH '{db}' AS old (READ_ONLY)")
    c.execute('''CREATE TABLE 매매 AS SELECT '서울특별시' AS 시도, '강남구' AS 시군구, '역삼동' AS 읍면동,단지명, 전용면적 AS "전용면적(㎡)", 계약년월, CAST(거래금액 AS VARCHAR) AS "거래금액(만원)", 층,건축년도,도로명,해제사유발생일,거래유형 FROM old.매매 WHERE 시군구 LIKE '서울%' ''')
    c.execute('''CREATE TABLE 전월세 AS SELECT '서울특별시' AS 시도, '강남구' AS 시군구, '역삼동' AS 읍면동,단지명, 전용면적 AS "전용면적(㎡)", 계약년월, CAST(보증금 AS VARCHAR) AS "보증금(만원)",층,건축년도,도로명,전월세구분,계약구분 FROM old.전월세''')
    c.close()
    a=compare(ext,q()).to_pylist()
    assert next(r for r in a if r['주소']=='서울특별시 강남구 길 1')['매매가격']==90000

def test_missing_contract_column_fails_explicitly(db):
    c=duckdb.connect(str(db)); c.execute('ALTER TABLE 전월세 DROP COLUMN 계약구분'); c.close()
    with pytest.raises(ValueError,match='계약구분'):
        compare(db,q())

@pytest.mark.parametrize('start,end',[(202613,202701),(202609,202608)])
def test_bad_month_rejected(start,end):
    with pytest.raises(ValueError): Query(start=start,end=end)

def test_read_only_missing_db_does_not_create(tmp_path):
    p=tmp_path/'missing.duckdb'
    with pytest.raises(FileNotFoundError): compare(p,q())
    assert not p.exists()

def test_external_road_number_difference_joins_by_lot(db):
    c=duckdb.connect(str(db))
    for t in ('매매','전월세'):
        c.execute(f'ALTER TABLE "{t}" ADD COLUMN 번지 VARCHAR')
        c.execute(f"UPDATE \"{t}\" SET 번지='0693-0' WHERE 도로명='길 1'")
    c.execute("UPDATE 매매 SET 도로명='고덕로',단지명='같은 단지' WHERE 번지 IS NOT NULL")
    c.execute("UPDATE 전월세 SET 도로명='고덕로 333' WHERE 번지 IS NOT NULL")
    c.execute("CREATE TABLE 공동주택_기본정보(단지코드 VARCHAR,도로명주소 VARCHAR,세대수 INTEGER)")
    c.execute("INSERT INTO 공동주택_기본정보 VALUES ('a','서울특별시 강남구 고덕로 333',1000)")
    c.close()
    rows=compare(db,q()).to_pylist()
    both=[r for r in rows if r['매매건수']==3 and r['전세건수']==2]
    assert len(both)==1
    assert both[0]['주소']=='서울특별시 강남구 역삼동 693'
    assert both[0]['세대수']==1000

def test_rural_lot_uses_ri_to_avoid_false_merge(db):
    c=duckdb.connect(str(db))
    for t in ('매매','전월세'):
        c.execute(f'ALTER TABLE "{t}" ADD COLUMN 번지 VARCHAR')
        c.execute(f'ALTER TABLE "{t}" ADD COLUMN 리 VARCHAR')
        c.execute(f"UPDATE \"{t}\" SET 시군구='경기도 평택시 포승읍',번지='1109',리='도곡리'")
    c.execute("UPDATE 전월세 SET 리='내기리'")
    c.close()
    rows=compare(db,q()).to_pylist()
    assert all(r['갭'] is None for r in rows)
    assert any('도곡리' in r['주소'] for r in rows)

def test_streamlit_controls_and_empty_result(db,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('GAP_DB_PATH',str(db))
    app=AppTest.from_file(str(Path('projects/chapter07_price_gap_table/dashboard/app.py').resolve()),default_timeout=20).run()
    assert not app.exception
    app.select_slider(key='period').set_value((202606,202608))
    app.checkbox(key='floor_enabled').check().run()
    assert not app.exception
    assert app.number_input(key='min_sale').value==1
    assert app.number_input(key='min_lease').value==1
    assert len(app.dataframe[0].value)==1
    assert app.dataframe[0].value['갭 (억원)'].notna().all()
    assert app.slider(key='floor_range').value==(2,100)
    app.slider(key='floor_range').set_value((1,1)).run()
    assert not app.exception and len(app.dataframe[0].value)==1
    assert app.dataframe[0].value['매매 (억원)'].iloc[0]==1.0
    assert app.dataframe[0].value['갭 (억원)'].isna().all()
    assert app.number_input(key='min_lease').disabled
    app.checkbox(key='floor_enabled').uncheck().run()
    assert not app.exception and len(app.dataframe[0].value)==1
    app.checkbox(key='floor_enabled').check().run()
    app.slider(key='floor_range').set_value((2,100)).run()
    app.number_input(key='min_sale').set_value(0)
    app.number_input(key='min_lease').set_value(0).run()
    assert not app.exception
    assert len(app.dataframe[0].value)==4
    assert app.dataframe[0].value['갭 (억원)'].isna().sum()==3
    app.number_input(key='min_sale').set_value(2)
    app.number_input(key='min_lease').set_value(2)
    app.selectbox(key='sort').set_value('매매가격')
    app.radio(key='direction').set_value('내림차순').run()
    assert not app.exception
    assert len(app.dataframe[0].value)==1
    app.number_input(key='min_sale').set_value(999).run()
    assert not app.exception and any('해당하는 결과가 없습니다' in x.value for x in app.info)


def test_floor_slider_limits_cover_collected_floors(db):
    from projects.chapter07_price_gap_table.dashboard.analysis import floor_limits
    assert floor_limits(db)==(1,100)
    c=duckdb.connect(str(db))
    c.execute('UPDATE 매매 SET 층=-2 WHERE 층=1')
    c.execute('UPDATE 전월세 SET 층=120')
    c.close()
    assert floor_limits(db)==(-2,120)


@pytest.mark.parametrize('empty', ['None', ' none ', 'NaN', 'NULL', '', '-', None])
def test_empty_cancellation_markers_keep_valid_sales(db, empty):
    c=duckdb.connect(str(db))
    c.execute("UPDATE 매매 SET 해제사유발생일=? WHERE 해제사유발생일 IS NULL OR 해제사유발생일='-'", [empty])
    c.close()
    row=next(r for r in compare(db,q()).to_pylist() if r['주소']=='서울특별시 강남구 길 1')
    assert (row['매매가격'],row['매매건수'],row['월중앙값고점'])==(90000,3,150000)


def add_nation(c, rows):
    c.execute("CREATE TABLE 공동주택_전국(단지고유번호 VARCHAR,주소 VARCHAR,단지명 VARCHAR,단지구분코드 VARCHAR,세대수 INTEGER,사용승인일 VARCHAR)")
    c.executemany('INSERT INTO 공동주택_전국 VALUES (?,?,?,?,?,?)',rows)


def test_chart_controls_share_table_filters(db, monkeypatch):
    import json
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv('GAP_DB_PATH', str(db))
    app = AppTest.from_file(str(Path('projects/chapter07_price_gap_table/dashboard/app.py').resolve()), default_timeout=20).run()
    app.select_slider(key='period').set_value((202606, 202608)).run()
    assert [tab.label for tab in app.tabs] == ['비교표', '차트 분석']

    def reconcile():
        assert not app.exception
        displayed = app.dataframe[0].value
        specs = [json.loads(chart.proto.spec) for chart in app.get('plotly_chart')]
        x, y = app.selectbox(key='scatter_x').value, app.selectbox(key='scatter_y').value
        metric = app.selectbox(key='distribution_metric').value
        assert sum(len(t['customdata']) for t in specs[0]['data']) == len(displayed.dropna(subset=[x, y]))
        assert len(specs[1]['data'][-1]['customdata']) == len(displayed.dropna(subset=[metric]))

    reconcile()
    from projects.chapter07_price_gap_table.dashboard import charts
    selected_ranges = {}

    def select_vertical(lower, upper, step, metric, key, height, top, bottom):
        selected = (round(lower+(upper-lower)*0.25, 2), round(lower+(upper-lower)*0.75, 2))
        selected_ranges[key] = list(selected)
        return selected

    monkeypatch.setattr(charts, 'vertical_range', select_vertical)
    lower, upper = app.slider(key='gap_scatter_x_range').value
    x_range = (round(lower+(upper-lower)*0.25, 2), round(lower+(upper-lower)*0.75, 2))
    app.slider(key='gap_scatter_x_range').set_value(x_range)
    app.run()
    reconcile()
    specs = [json.loads(chart.proto.spec) for chart in app.get('plotly_chart')]
    assert specs[0]['layout']['yaxis']['range'] == selected_ranges['gap_scatter_y_range']
    assert specs[1]['layout']['yaxis']['range'] == selected_ranges['gap_distribution_y_range']
    assert specs[0]['layout']['xaxis']['range'] == list(x_range)
    app.number_input(key='min_sale').set_value(0)
    app.number_input(key='min_lease').set_value(0).run()
    reconcile()
    app.selectbox(key='scatter_x').set_value('매매 건수')
    app.selectbox(key='scatter_y').set_value('신규 전세 (억원)')
    app.selectbox(key='scatter_group').set_value('읍면동')
    app.selectbox(key='distribution_metric').set_value('전세가율 (%)')
    app.selectbox(key='distribution_group').set_value('시도').run()
    reconcile()
    app.select_slider(key='period').set_value((202501, 202608)).run()
    reconcile()
    app.checkbox(key='gap_enabled').check().run()
    reconcile()
    app.number_input(key='min_sale').set_value(999).run()
    assert not app.exception and not app.get('plotly_chart')


def test_nationwide_metadata_by_lot_without_lease_road(db):
    c=duckdb.connect(str(db))
    for t in ('매매','전월세'):
        c.execute(f'ALTER TABLE {t} ADD COLUMN 지번 VARCHAR')
        c.execute(f"UPDATE {t} SET 지번='0693-0',도로명='고덕로' WHERE 도로명='길 1'")
    add_nation(c,[('a','서울특별시 강남구 역삼동 693','같은 단지','1',1000,'20000101'),
                  ('v','서울특별시 강남구 역삼동 693','같은단지','3',12,'20000101')])
    c.close()
    row=next(r for r in compare(db,q()).to_pylist() if r['주소']=='서울특별시 강남구 역삼동 693')
    assert (row['매매건수'],row['전세건수'],row['세대수'])==(3,2,1000)


def test_reader_metadata_unique_location_name_year(db):
    c=duckdb.connect(str(db))
    # 같은 이름의 별도 주소가 존재하면 이름으로 메타를 가져오지 않는다.
    c.execute("UPDATE 매매 SET 단지명='별도단지' WHERE 도로명='길 2'")
    add_nation(c,[('a','서울특별시 강남구 역삼동 693','같은 단지','1',1000,'20000101'),
                  ('b','경기도 광주시 역동 1','같은단지','1',300,'20100101')])
    c.close()
    rows=compare(db,q()).to_pylist()
    assert next(r for r in rows if r['주소']=='서울특별시 강남구 길 1')['세대수']==1000
    assert next(r for r in rows if r['시도']=='경기도')['세대수']==300
    assert next(r for r in rows if r['단지명']=='별도단지')['세대수'] is None


@pytest.mark.parametrize('conflict', ['trade_address','master_address','year'])
def test_reader_metadata_ambiguous_match_stays_missing(db,conflict):
    c=duckdb.connect(str(db))
    if conflict!='trade_address': c.execute("DELETE FROM 매매 WHERE 도로명='길 2'")
    rows=[('a','서울특별시 강남구 역삼동 693','같은단지','1',1000,'20000101')]
    if conflict=='master_address': rows.append(('b','서울특별시 강남구 역삼동 694','같은단지','1',500,'20000101'))
    if conflict=='year': rows=[('a','서울특별시 강남구 역삼동 693','같은단지','1',1000,'20100101')]
    add_nation(c,rows);c.close()
    assert next(r for r in compare(db,q()).to_pylist() if r['주소']=='서울특별시 강남구 길 1')['세대수'] is None


def test_one_sided_lot_column_does_not_split_reader_trades(db):
    c=duckdb.connect(str(db));c.execute('ALTER TABLE 매매 ADD COLUMN 지번 VARCHAR')
    c.execute("UPDATE 매매 SET 지번='693' WHERE 도로명='길 1'");c.close()
    assert next(r for r in compare(db,q()).to_pylist() if r['주소']=='서울특별시 강남구 길 1')['갭']==40000


def test_period_slider_single_month_and_cross_year(db,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('GAP_DB_PATH',str(db))
    app=AppTest.from_file('projects/chapter07_price_gap_table/dashboard/app.py',default_timeout=20).run()
    app.select_slider(key='period').set_value((202501,202606)).run()
    assert not app.exception
    assert any('2025년 1월–2026년 6월' in m.value for m in app.markdown)
    app.select_slider(key='period').set_value((202608,202608)).run()
    assert not app.exception
    assert any('2026년 8월–2026년 8월' in m.value for m in app.markdown)
    c=duckdb.connect(str(db))
    for t in ('매매','전월세'): c.execute(f'DELETE FROM {t} WHERE 계약년월<>202608')
    c.close()
    app=AppTest.from_file('projects/chapter07_price_gap_table/dashboard/app.py',default_timeout=20).run()
    assert not app.exception
    assert app.select_slider(key='period').value==(202608,202608)


def test_unique_lot_and_year_resolve_different_metadata_name(db):
    c=duckdb.connect(str(db))
    for t in ('매매','전월세'):
        c.execute(f'ALTER TABLE {t} ADD COLUMN 번지 VARCHAR')
        c.execute(f"UPDATE {t} SET 번지='693' WHERE 도로명='길 1'")
    add_nation(c,[('a','서울특별시 강남구 역삼동 693','같은단지 같은아파트','1',1000,'20000101')])
    c.close()
    row=next(r for r in compare(db,q()).to_pylist() if r['주소']=='서울특별시 강남구 역삼동 693')
    assert row['세대수']==1000


@pytest.mark.parametrize('conflict',['master','trade','year'])
def test_lot_only_metadata_ambiguity_stays_missing(db,conflict):
    c=duckdb.connect(str(db))
    for t in ('매매','전월세'):
        c.execute(f'ALTER TABLE {t} ADD COLUMN 번지 VARCHAR')
        c.execute(f"UPDATE {t} SET 번지='693' WHERE 도로명='길 1'")
    rows=[('a','서울특별시 강남구 역삼동 693','이름표기차이','1',1000,'20000101')]
    if conflict=='master': rows.append(('b','서울특별시 강남구 역삼동 693','별도관리단지','1',500,'20000101'))
    if conflict=='trade': c.execute("UPDATE 매매 SET 번지='693',단지명='다른단지' WHERE 도로명='길 2'")
    if conflict=='year': rows=[('a','서울특별시 강남구 역삼동 693','이름표기차이','1',1000,'20200101')]
    add_nation(c,rows);c.close()
    assert all(r['세대수'] is None for r in compare(db,q()).to_pylist() if r['주소']=='서울특별시 강남구 역삼동 693')
