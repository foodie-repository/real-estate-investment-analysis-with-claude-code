"""전세 자료가 없는 기간에도 매매 정보와 차트를 제공한다."""
import json
import duckdb
import pytest
from streamlit.testing.v1 import AppTest
from tests.part07.test_analysis import db
from tests.part07.test_period_rules import history


@pytest.fixture
def app(history,monkeypatch):
    c=duckdb.connect(str(history))
    c.execute('DELETE FROM 전월세 WHERE 계약년월<201101');c.close()
    monkeypatch.setenv('GAP_DB_PATH',str(history))
    return AppTest.from_file('projects/chapter07_price_gap_table/dashboard/app.py',default_timeout=20).run()


def test_sale_only_period_shows_prices_peaks_and_two_charts(app):
    app.select_slider(key='period').set_value((201012,201012)).run()
    assert not app.exception
    assert app.dataframe, '전세가 없는 기간에도 매매 행을 표시해야 한다.'
    row=app.dataframe[0].value.iloc[0]
    assert row['매매 (억원)']==10 and row['매매 건수']==2
    assert row['전고점 (억원)']==10 and row['전고점 대비 (%)']==100
    assert app.dataframe[0].value[['전세 (억원)','갭 (억원)','전세가율 (%)']].isna().all().all()
    assert app.number_input(key='min_lease').value==0
    assert app.number_input(key='min_lease').disabled
    assert app.checkbox(key='gap_enabled').disabled
    assert any('매매 정보' in msg.value for msg in app.info)
    assert app.selectbox(key='scatter_x').value=='매매 (억원)'
    assert app.selectbox(key='distribution_metric').value=='매매 (억원)'
    specs=[json.loads(v.proto.spec) for v in app.get('plotly_chart')]
    assert len(specs)==2
    assert specs[0]['layout']['xaxis']['title']['text']=='매매 (억원)'
    assert specs[1]['layout']['yaxis']['title']['text']=='매매 (억원)'


def test_sale_only_period_preserves_and_restores_comparison_choices(app):
    app.number_input(key='min_lease').set_value(2).run()
    app.checkbox(key='lease_price_enabled').check().run()
    lease_range=app.slider(key='lease_range').value
    app.checkbox(key='gap_enabled').check().run()
    app.number_input(key='gap_min').set_value(0.5)
    app.number_input(key='gap_max').set_value(8.5)
    app.selectbox(key='sort').set_value('갭').run()
    app.select_slider(key='period').set_value((201012,201012)).run()
    assert app.dataframe
    assert app.number_input(key='min_lease').value==0
    assert not app.checkbox(key='gap_enabled').value
    assert not app.checkbox(key='lease_price_enabled').value
    assert app.checkbox(key='lease_price_enabled').disabled
    assert app.selectbox(key='sort').value=='고점대비'
    app.select_slider(key='period').set_value((202111,202111)).run()
    assert not app.exception
    assert app.number_input(key='min_lease').value==2
    assert not app.number_input(key='min_lease').disabled
    assert app.checkbox(key='gap_enabled').value
    assert app.checkbox(key='lease_price_enabled').value
    assert app.slider(key='lease_range').value==lease_range
    assert not app.checkbox(key='gap_enabled').disabled
    assert app.number_input(key='gap_min').value==0.5
    assert app.number_input(key='gap_max').value==8.5
    assert app.selectbox(key='sort').value=='갭'


def test_cross_period_with_lease_keeps_normal_minimum(app):
    app.select_slider(key='period').set_value((201012,201101)).run()
    assert not app.exception and app.dataframe
    assert app.number_input(key='min_lease').value==1
    assert not app.number_input(key='min_lease').disabled
    assert app.dataframe[0].value['갭 (억원)'].notna().all()


def test_chart_choices_return_after_sale_only_period(app):
    app.selectbox(key='scatter_x').set_value('전세가율 (%)').run()
    app.selectbox(key='distribution_metric').set_value('신규 전세 (억원)').run()
    app.select_slider(key='period').set_value((201012,201012)).run()
    assert app.selectbox(key='scatter_x').value=='매매 (억원)'
    assert app.selectbox(key='distribution_metric').value=='매매 (억원)'
    app.select_slider(key='period').set_value((202111,202111)).run()
    assert not app.exception
    assert app.selectbox(key='scatter_x').value=='전세가율 (%)'
    assert app.selectbox(key='distribution_metric').value=='신규 전세 (억원)'
