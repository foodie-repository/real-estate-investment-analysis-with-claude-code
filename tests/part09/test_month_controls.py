from streamlit.testing.v1 import AppTest


SCRIPT = '''
import streamlit as st
from projects.chapter09_price_volume.dashboard.controls import select_base_month

narrow = st.checkbox("기간 축소")
single = st.checkbox("한 달만")
months = [202501] if single else [202412, 202502]
if narrow:
    months = [202502, 202503]
selected = select_base_month(months, 202502 if narrow else months[0])
st.write(selected)
'''


def test_buttons_move_one_calendar_month_and_follow_slider():
    at = AppTest.from_string(SCRIPT).run()
    assert not at.exception
    assert at.button(key="base_month_prev").disabled
    at.button(key="base_month_next").click().run()
    # 거래가 전혀 없는 1월도 건너뛰지 않고, 연도 경계를 넘는다.
    assert at.select_slider(key="base_month").value == 202501
    at.button(key="base_month_next").click().run()
    assert at.select_slider(key="base_month").value == 202502
    assert at.button(key="base_month_next").disabled
    at.select_slider(key="base_month").set_value(202501).run()
    at.button(key="base_month_prev").click().run()
    assert at.select_slider(key="base_month").value == 202412
    assert at.markdown[-1].value == "`202412`"


def test_period_changes_preserve_valid_month_and_reset_outside_month():
    at = AppTest.from_string(SCRIPT).run()
    assert not at.exception
    at.select_slider(key="base_month").set_value(202502).run()
    at.checkbox[0].check().run()
    assert at.select_slider(key="base_month").value == 202502
    at.select_slider(key="base_month").set_value(202503).run()
    at.checkbox[0].uncheck().run()
    assert not at.exception
    assert at.select_slider(key="base_month").value == 202412


def test_single_month_disables_navigation_without_slider_error():
    at = AppTest.from_string(SCRIPT).run()
    assert not at.exception
    at.checkbox[1].check().run()
    assert not at.exception
    assert at.button(key="base_month_prev").disabled
    assert at.button(key="base_month_next").disabled
    assert at.markdown[-1].value == "`202501`"
