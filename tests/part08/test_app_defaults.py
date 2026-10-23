from streamlit.testing.v1 import AppTest
from tests.sample_data import create_sample_database


def test_ranking_count_defaults_to_fifty(tmp_path, monkeypatch):
    path = create_sample_database(tmp_path / 'sample.duckdb')
    monkeypatch.setenv('TRADE_MAP_DB_PATH', str(path))
    monkeypatch.setenv('VWORLD_API_KEY', 'synthetic-test-key')
    app = AppTest.from_file('projects/chapter08_trade_map/dashboard/app.py', default_timeout=30).run()
    assert not app.exception
    assert next(w for w in app.select_slider if w.label == '랭킹 표시 개수').value == 50
    assert any('상위 50개' in c.value for c in app.caption)


def test_map_handles_non_seoul_database(tmp_path, monkeypatch):
    path = create_sample_database(tmp_path / 'busan.duckdb', sido='부산광역시')
    monkeypatch.setenv('TRADE_MAP_DB_PATH', str(path))
    monkeypatch.setenv('VWORLD_API_KEY', 'synthetic-test-key')
    import streamlit as st
    st.cache_data.clear()
    app = AppTest.from_file('projects/chapter08_trade_map/dashboard/app.py', default_timeout=30).run()
    assert not app.exception
    assert next(w for w in app.multiselect if w.label == '시도').value == ['부산광역시']
