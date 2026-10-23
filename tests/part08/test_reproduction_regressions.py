"""독자 재현 비교에서 발견한 연도 초기화와 좌표 조인 회귀를 검증한다."""
import duckdb
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from tests.part08.test_coordinate_key import _create_coordinate_key_db


@pytest.fixture
def reader_db(tmp_path, monkeypatch):
    path = tmp_path / "reader.duckdb"
    _create_coordinate_key_db(path)
    with duckdb.connect(str(path)) as con:
        con.execute("INSERT INTO 매매 SELECT 시군구, 단지명, 전용면적, 200601, 건축년도, 도로명, 거래금액, 해제사유발생일, 거래유형 FROM 매매 LIMIT 1")
        con.execute("INSERT INTO 전월세 SELECT 시군구, 단지명, 전용면적, 계약년월, 건축년도, 도로명, '전세', 50000 FROM 매매 WHERE 계약년월 = 202501")
        con.execute("INSERT INTO 전월세 SELECT 시군구, 단지명, 전용면적, 201101, 건축년도, 도로명, '전세', 보증금 FROM 전월세 LIMIT 1")
        con.execute("INSERT INTO 전월세 SELECT 시군구, 단지명, 전용면적, 계약년월, 건축년도, 도로명, '월세', 보증금 FROM 전월세")
    monkeypatch.setenv("TRADE_MAP_DB_PATH", str(path))
    st.cache_data.clear()
    yield path
    st.cache_data.clear()


def _widget(app, kind, label):
    return next(w for w in getattr(app, kind) if w.label == label)


def test_selected_year_survives_trade_type_and_mode_changes(reader_db):
    app = AppTest.from_file("projects/chapter08_trade_map/dashboard/app.py").run()
    _widget(app, "slider", "기간 (연도)").set_value(2024).run()
    _widget(app, "radio", "거래유형").set_value("전세").run()
    assert not app.exception
    assert _widget(app, "slider", "기간 (연도)").value == 2024
    _widget(app, "checkbox", "기간 범위 모드").check().run()
    _widget(app, "slider", "기간 (연도)").set_value((2013, 2020)).run()
    _widget(app, "radio", "거래유형").set_value("매매").run()
    assert _widget(app, "slider", "기간 (연도)").value == (2013, 2020)
    _widget(app, "checkbox", "기간 범위 모드").uncheck().run()
    assert _widget(app, "slider", "기간 (연도)").value == 2024
    assert all("Session State" not in w.value for w in app.warning)
    _widget(app, "button", "다음 ▶").click().run()
    assert _widget(app, "slider", "기간 (연도)").value == 2025
    _widget(app, "button", "◀ 이전").click().run()
    assert _widget(app, "slider", "기간 (연도)").value == 2024


def test_year_is_clamped_to_new_trade_range(reader_db):
    app = AppTest.from_file("projects/chapter08_trade_map/dashboard/app.py").run()
    _widget(app, "slider", "기간 (연도)").set_value(2006).run()
    _widget(app, "radio", "거래유형").set_value("월세").run()
    assert not app.exception
    assert _widget(app, "slider", "기간 (연도)").value == 2011


def test_single_available_year_is_rendered_without_slider_error(reader_db):
    with duckdb.connect(str(reader_db)) as con:
        con.execute("DELETE FROM 매매 WHERE 계약년월 != 202501")
    app = AppTest.from_file("projects/chapter08_trade_map/dashboard/app.py").run()
    assert not app.exception
    assert "2025년" in app.caption[0].value
    _widget(app, "checkbox", "기간 범위 모드").check().run()
    assert not app.exception
    assert "2025년" in app.caption[0].value


def test_normalized_coordinates_do_not_multiply_trades(reader_db):
    from projects.chapter08_trade_map.dashboard.pivot import generate_pivot_table

    with duckdb.connect(str(reader_db)) as con:
        con.execute("DELETE FROM 좌표 WHERE 도로명주소 LIKE '서울특별시 강남구%'")
        con.execute("INSERT INTO 좌표 VALUES ('  서울특별시  강남구 같은로 1 ', 127, 37), ('서울특별시 강남구 같은로 1  ', 128, 38)")
    result = generate_pivot_table("매매", "서울특별시", "강남구", 연도_시작=2025, 연도_끝=2025)
    assert len(result) == 1
    assert result.iloc[0]["거래량"] == 1
    assert (result.iloc[0]["경도"], result.iloc[0]["위도"]) == (127, 37)


def test_same_length_address_uses_deterministic_coordinate_pair(reader_db):
    from projects.chapter08_trade_map.dashboard.pivot import generate_pivot_table

    with duckdb.connect(str(reader_db)) as con:
        con.execute("UPDATE 매매 SET 도로명 = '나나로 1' WHERE 단지명 = '강남단지'")
        con.execute("INSERT INTO 매매 SELECT 시군구, 단지명, 전용면적, 202401, 건축년도, '가가로 1', 거래금액, 해제사유발생일, 거래유형 FROM 매매 WHERE 단지명 = '강남단지' LIMIT 1")
        con.execute("INSERT INTO 좌표 VALUES ('서울특별시 강남구 나나로 1', 129, 39), ('서울특별시 강남구 가가로 1', 126, 36)")
    result = generate_pivot_table("매매", "서울특별시", "강남구", 연도_시작=2025, 연도_끝=2025)
    assert len(result) == 1
    assert (result.iloc[0]["경도"], result.iloc[0]["위도"]) == (126, 36)


@pytest.mark.parametrize("blank_road", ["  ", "\t", "\n"])
def test_whitespace_only_road_is_excluded_from_trade_count(reader_db, blank_road):
    from projects.chapter08_trade_map.dashboard.pivot import generate_pivot_table

    with duckdb.connect(str(reader_db)) as con:
        con.execute("INSERT INTO 매매 SELECT 시군구, 단지명, 전용면적, 202501, 건축년도, ?, 거래금액, 해제사유발생일, 거래유형 FROM 매매 WHERE 단지명 = '강남단지' LIMIT 1", [blank_road])
    result = generate_pivot_table("매매", "서울특별시", "강남구", 연도_시작=2025, 연도_끝=2025)
    assert result["거래량"].sum() == 1


@pytest.mark.parametrize("blank_road", ["  ", "\t", "\n"])
def test_empty_road_cannot_supply_a_region_center_coordinate(reader_db, blank_road):
    from projects.chapter08_trade_map.dashboard.pivot import generate_pivot_table

    with duckdb.connect(str(reader_db)) as con:
        con.execute("DELETE FROM 좌표 WHERE 도로명주소 LIKE '서울특별시 강남구%'")
        con.execute("INSERT INTO 좌표 VALUES ('서울특별시 강남구', 127, 37)")
        con.execute("INSERT INTO 매매 SELECT 시군구, 단지명, 전용면적, 202401, 건축년도, ?, 거래금액, 해제사유발생일, 거래유형 FROM 매매 WHERE 단지명 = '강남단지' LIMIT 1", [blank_road])
    result = generate_pivot_table("매매", "서울특별시", "강남구", 연도_시작=2025, 연도_끝=2025)
    assert result.empty
