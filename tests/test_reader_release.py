import importlib
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from tests.sample_data import create_sample_database


def test_trade_refresh_preserves_other_regions_and_years(tmp_path, monkeypatch):
    m=importlib.import_module('src.collectors.실거래가'); path=tmp_path/'nested'/'trade.duckdb'
    monkeypatch.setattr(m,'DB_PATH',str(path))
    initial=pd.DataFrame({'시군구':['서울특별시 강남구 역삼동','부산광역시 해운대구 우동','서울특별시 강남구 역삼동'],'계약년월':[202501,202501,202401],'거래금액':[1,2,3]})
    m.save_to_duckdb(initial.iloc[:2], '매매',2025)
    m.save_to_duckdb(initial.iloc[2:], '매매',2024)
    new=initial.iloc[:1].copy();new['거래금액']=100
    m.save_to_duckdb(new,'매매',2025,'서울특별시')
    m.save_to_duckdb(new,'매매',2025,'서울특별시')
    with duckdb.connect(str(path),read_only=True) as c:
        assert c.execute('SELECT 거래금액 FROM 매매 ORDER BY 거래금액').fetchall()==[(2,),(3,),(100,)]
    bad=new.copy();bad['예상밖컬럼']=1
    with pytest.raises(duckdb.Error):m.save_to_duckdb(bad,'매매',2025,'서울특별시')
    with duckdb.connect(str(path),read_only=True) as c: assert c.execute('SELECT COUNT(*) FROM 매매').fetchone()[0]==3


def test_housing_refresh_preserves_other_regions(tmp_path,monkeypatch):
    m=importlib.import_module('src.collectors.공동주택'); path=tmp_path/'housing.duckdb';monkeypatch.setattr(m,'DB_PATH',str(path))
    df=pd.DataFrame({'주소':['서울특별시 강남구 역삼동 1','부산광역시 해운대구 우동 1'],'세대수':[100,200]})
    m.save_to_duckdb(df)
    new=df.iloc[:1].copy();new['세대수']=300
    m.save_to_duckdb(new,'서울특별시')
    with duckdb.connect(str(path),read_only=True) as c: assert c.execute('SELECT 세대수 FROM 공동주택_전국 ORDER BY 세대수').fetchall()==[(200,),(300,)]


def test_partial_api_failure_does_not_save(monkeypatch):
    m=importlib.import_module('src.collectors.실거래가')
    monkeypatch.setattr(m,'PUBLIC_DATA_API_KEY','test')
    monkeypatch.setattr(m,'TransactionPrice',lambda key:object())
    monkeypatch.setattr(m,'get_sigungu_codes',lambda sido:pd.DataFrame({'시군구코드':['1']}))
    monkeypatch.setattr(m,'collect_매매',lambda *a:(pd.DataFrame({'계약년월':[202501]}),['test failure']))
    def forbidden(*args):pytest.fail('partial response must not replace database')
    monkeypatch.setattr(m,'save_to_duckdb',forbidden)
    monkeypatch.setattr('sys.argv',['collector','--year','2025','--type','매매'])
    with pytest.raises(SystemExit) as exc:m.main()
    assert exc.value.code==1


def test_tracking_does_not_mix_same_named_complexes(tmp_path,monkeypatch):
    from projects.chapter04_tracking import tracker
    path=create_sample_database(tmp_path/'sample.duckdb')
    with duckdb.connect(str(path)) as c:
        c.execute("INSERT INTO 매매 SELECT '부산광역시 해운대구 우동',지번,단지명,전용면적,202610,계약일,99999999,층,건축년도,도로명,NULL,거래유형 FROM 매매 WHERE 단지명='검증단지1' LIMIT 1")
        c.execute("INSERT INTO 전월세 SELECT '부산광역시 해운대구 우동',지번,단지명,전월세구분,전용면적,202610,계약일,88888888,월세금,층,건축년도,도로명,계약구분 FROM 전월세 WHERE 단지명='검증단지1' LIMIT 1")
        c.execute("UPDATE 매매 SET 해제사유발생일='-' WHERE 계약년월=202609")
    monkeypatch.setattr(tracker,'DB_PATH',str(path))
    row=tracker.get_tracking_data([{'시군구':'서울특별시 강남구 역삼동','단지명':'검증단지1','전용면적':84.}])[0]
    assert row['기준월']==202609 and row['데이터최신월']==202609
    assert row['최근매매가']==88910 and row['매매거래건수']==3
    assert row['전고점']<99999999


@pytest.mark.parametrize('chapter,module,var',[(6,'chapter06_kb_dashboard','KB_DB_PATH'),(9,'chapter09_price_volume','PRICE_DB_PATH')])
def test_blank_optional_database_uses_default(chapter,module,var,monkeypatch):
    m=importlib.import_module(f'projects.{module}.dashboard.db')
    previous=m._DB_PATH
    try:
        monkeypatch.setenv(var,'');importlib.reload(m)
        from src.config import DB_PATH
        assert m._DB_PATH==DB_PATH
    finally:m._DB_PATH=previous


@pytest.mark.parametrize('folder,var',[('chapter06_kb_dashboard','KB_DB_PATH'),('chapter07_price_gap_table','GAP_DB_PATH'),('chapter08_trade_map','TRADE_MAP_DB_PATH'),('chapter09_price_volume','PRICE_DB_PATH')])
def test_missing_database_shows_setup_message(folder,var,tmp_path,monkeypatch):
    import streamlit as st
    st.cache_data.clear();st.cache_resource.clear()
    missing=str(tmp_path/'missing.duckdb');monkeypatch.setenv(var,missing)
    if folder in ('chapter06_kb_dashboard','chapter09_price_volume'):
        monkeypatch.setattr(importlib.import_module(f'projects.{folder}.dashboard.db'),'_DB_PATH',missing)
    app=AppTest.from_file(f'projects/{folder}/dashboard/app.py',default_timeout=20).run()
    assert not app.exception and app.error
    assert not Path(missing).exists()


def test_watchlist_disambiguates_regions(tmp_path, monkeypatch):
    from projects.chapter04_tracking import watchlist
    path=create_sample_database(tmp_path/'sample.duckdb')
    with duckdb.connect(str(path)) as con:
        con.execute("INSERT INTO 매매 SELECT '부산광역시 해운대구 우동',지번,단지명,전용면적,계약년월,계약일,거래금액,층,건축년도,도로명,해제사유발생일,거래유형 FROM 매매 LIMIT 1")
    monkeypatch.setattr(watchlist,'DB_PATH',str(path))
    monkeypatch.setattr(watchlist,'WATCHLIST_PATH',tmp_path/'watchlist.json')
    watchlist.add('검증단지1',84.)
    assert watchlist.get_all()==[]
    for region in ('서울특별시 강남구 역삼동','부산광역시 해운대구 우동'):
        watchlist.add('검증단지1',84.,region)
    assert len(watchlist.get_all())==2
    watchlist.remove('검증단지1',84.)
    assert len(watchlist.get_all())==2
    watchlist.remove('검증단지1',84.,'서울특별시 강남구 역삼동')
    assert [row['시군구'] for row in watchlist.get_all()]==['부산광역시 해운대구 우동']


def test_kb_timeseries_with_only_one_region(tmp_path,monkeypatch):
    import streamlit as st
    from tests.sample_data import create_sample_boundary
    from projects.chapter06_kb_dashboard.dashboard import db, geo
    st.cache_data.clear();st.cache_resource.clear()
    path=create_sample_database(tmp_path/'sample.duckdb')
    boundary=create_sample_boundary(tmp_path/'boundary.geojson')
    monkeypatch.setattr(db,'_DB_PATH',str(path))
    monkeypatch.setattr(geo,'GEOJSON_PATH',boundary)
    app=AppTest.from_file('projects/chapter06_kb_dashboard/dashboard/app.py',default_timeout=30).run()
    assert not app.exception
    app.radio[0].set_value('시계열 분석').run()
    assert not app.exception
    assert app.multiselect(key='ts_sido').value==['서울']
