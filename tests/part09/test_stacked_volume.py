"""누적 거래량의 월 합계, 결측 달, 거래유형 분리 및 축 범위를 검증한다."""
import json
from collections import defaultdict

import pandas as pd
from streamlit.testing.v1 import AppTest

from projects.chapter09_price_volume.dashboard.charts import create_scatter_chart, create_line_chart


def test_both_views_stack_exact_counts_with_empty_month_and_rent_only_target():
    records = {
        '매매': [('A', 202501, 2), ('B', 202501, 3), ('A', 202503, 1)],
        '전세': [('A', 202501, 4), ('C', 202503, 2)],
    }
    individual, monthly = {}, {}
    for kind, groups in records.items():
        individual[kind] = pd.DataFrame([
            dict(계약년월=month, 비교대상=name, 단지명=name, 평형대='30평대',
                 전용면적=84., 추정평형=33, 층=10, 가격_억=5.)
            for name, month, count in groups for _ in range(count)])
        monthly[kind] = pd.DataFrame([
            dict(계약년월=month, 비교대상=name, 중위가_억=5., 거래량=count)
            for name, month, count in groups])
    for fig in (create_scatter_chart(individual), create_line_chart(monthly)):
        assert fig.layout.barmode == 'stack'
        assert {t.name for t in fig.data if t.showlegend} == {'A', 'B', 'C'}
        for axis, expected in [('y3', [5, 0, 1]), ('y4', [4, 0, 2])]:
            bars = [t for t in fig.data if t.type == 'bar' and t.yaxis == axis]
            totals = defaultdict(int)
            for bar in bars:
                assert not bar.offsetgroup
                for month, count in zip(bar.x, bar.y):
                    totals[month] += count
                assert "합계" not in bar.hovertemplate
                price = next(t for t in fig.data if t.type == 'scatter' and t.legendgroup == bar.legendgroup)
                assert bar.marker.color == (price.line.color or price.marker.color)
            assert list(totals.values()) == expected


def test_volume_slider_fits_stack_sum_not_largest_segment():
    app = AppTest.from_string('''
import streamlit as st
import pandas as pd
from projects.chapter09_price_volume.dashboard.charts import create_line_chart
from projects.chapter09_price_volume.dashboard.axis_controls import render_axis_controls
data = {"매매": pd.DataFrame({"계약년월":[202501,202501], "비교대상":["A","B"],
    "중위가_억":[10.,12.], "거래량":[40,60]})}
fig = create_line_chart(data)
render_axis_controls(fig, "stack-test")
st.json({"range": list(fig.layout.yaxis2.range), "tick": fig.layout.yaxis2.dtick})
''').run()
    assert not app.exception
    result = json.loads(app.json[0].value)
    assert result['range'][0] == 0
    assert result['range'][1] > 100
    assert result['tick'] == int(result['tick'])
