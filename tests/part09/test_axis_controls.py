"""표시 범위 변경이 기준월 계산과 거래량을 바꾸지 않는지 검증한다."""
import json

import pandas as pd
from streamlit.testing.v1 import AppTest


def test_common_period_zoom_preserves_prices_volumes_and_base_month():
    app = AppTest.from_string('''
import streamlit as st
import pandas as pd
from projects.chapter09_price_volume.dashboard.charts import create_line_chart
from projects.chapter09_price_volume.dashboard.axis_controls import render_axis_controls
data = {kind: pd.DataFrame({"계약년월": [202501, 202503],
    "비교대상": ["테스트 · 30평대"]*2, "중위가_억": prices, "거래량": [1, 3]})
    for kind, prices in [("매매", [10., 12.]), ("전세", [5., 6.])]}
fig = create_line_chart(data, base_month=202501)
render_axis_controls(fig, "test")
st.json({"ranges": [[str(value) for value in fig.layout[name].range] for name in
    ["xaxis", "xaxis2", "xaxis3", "xaxis4"]],
    "prices": [None if pd.isna(value) else float(value) for value in fig.data[1].y],
    "volume": [int(value) for value in fig.data[2].y],
    "baselines": [shape.y0 for shape in fig.layout.shapes]})
''').run()
    assert not app.exception
    app.select_slider[0].set_value((pd.Timestamp("2025-02-01"), pd.Timestamp("2025-03-01"))).run()
    assert not app.exception
    result = json.loads(app.json[0].value)
    assert all(r == result["ranges"][0] for r in result["ranges"])
    assert result["ranges"][0][0].startswith("2025-01-17")
    assert result["prices"] == [100., None, 120.]
    assert result["volume"] == [1, 0, 3]
    assert result["baselines"] == [100, 100]


def test_single_month_has_visible_bars_without_an_invalid_period_slider():
    app = AppTest.from_string('''
import streamlit as st
import pandas as pd
from projects.chapter09_price_volume.dashboard.charts import create_line_chart
from projects.chapter09_price_volume.dashboard.axis_controls import render_axis_controls
data = {"전세": pd.DataFrame({"계약년월": [202501],
    "비교대상": ["테스트"], "중위가_억": [5.], "거래량": [1]})}
fig = create_line_chart(data)
render_axis_controls(fig, "single")
st.json({"x": [str(value) for value in fig.layout.xaxis.range],
         "volume_range": list(fig.layout.yaxis2.range), "tick": fig.layout.yaxis2.dtick})
''').run()
    assert not app.exception
    assert not app.select_slider
    result = json.loads(app.json[0].value)
    assert result["x"] == ["2024-12-17 00:00:00", "2025-01-16 00:00:00"]
    assert result["volume_range"][0] == 0
    assert result["volume_range"][1] > 1
    assert result["tick"] == 1


def test_scatter_controls_are_independent_and_include_full_selected_months():
    app = AppTest.from_string('''
import streamlit as st
import pandas as pd
from projects.chapter09_price_volume.dashboard.charts import create_scatter_chart, create_line_chart
from projects.chapter09_price_volume.dashboard.axis_controls import render_axis_controls
trades = pd.DataFrame({"계약년월": [202501]*4+[202502]*4+[202503]*4,
    "단지명": ["A"]*12, "평형대": ["30평대"]*12, "비교대상": ["A · 30평대"]*12,
    "가격_억": [10.]*12, "전용면적": [84.]*12, "층": [10]*12, "추정평형": [33]*12})
individual = create_scatter_chart({"매매":trades,"전세":trades})
monthly = create_line_chart({"매매": pd.DataFrame({"계약년월":[202501,202503],
    "비교대상":["A","A"], "중위가_억":[10.,12.], "거래량":[4,4]})})
a,b=st.tabs(["개별", "중위가"])
with a:
    render_axis_controls(individual,"individual")
with b:
    render_axis_controls(monthly,"monthly_price")
st.json({"ranges":[[str(v) for v in individual.layout[n].range] for n in
    ["xaxis","xaxis2","xaxis3","xaxis4"]], "data":individual.to_json(),
    "monthly_range":[str(v) for v in monthly.layout.xaxis.range]})
''').run()
    assert not app.exception
    before = json.loads(app.json[0].value)
    assert before['ranges'][0] == ['2025-01-01 00:00:00', '2025-04-01 00:00:00']
    app.select_slider(key='individual_x_range').set_value(
        (pd.Timestamp('2025-02-01'), pd.Timestamp('2025-03-01'))).run()
    assert not app.exception
    after = json.loads(app.json[0].value)
    assert all(r == ['2025-02-01 00:00:00', '2025-04-01 00:00:00'] for r in after['ranges'])
    assert after['monthly_range'] == before['monthly_range']
    assert json.loads(after['data'])['data'] == json.loads(before['data'])['data']
    bars = [t for t in json.loads(after['data'])['data'] if t['type']=='bar']
    assert all(t['xperiod'] == 'M1' and t['xperiodalignment'] == 'middle' for t in bars)


def test_scatter_points_stay_fixed_when_query_tie_order_changes():
    from projects.chapter09_price_volume.dashboard.charts import create_scatter_chart

    trades = pd.DataFrame({
        '계약년월':[202501]*4, '단지명':['A','B','A','B'],
        '비교대상':['A · 30평대','B · 40평대','A · 30평대','B · 40평대'],
        '평형대':['30평대','40평대','30평대','40평대'],
        '가격_억':[10.,15.,11.,16.], '전용면적':[84.,114.,84.,114.],
        '층':[10,12,15,16], '추정평형':[33,45,33,45],
    })
    original = trades.copy(deep=True)
    first = create_scatter_chart({'매매':trades})
    reordered = create_scatter_chart({'매매':trades.iloc[::-1]})
    assert first.to_json() == reordered.to_json()
    pd.testing.assert_frame_equal(trades, original)
