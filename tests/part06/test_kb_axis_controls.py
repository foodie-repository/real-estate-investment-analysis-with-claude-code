"""축 범위 조절이 기준값이나 원본 데이터를 바꾸지 않는지 확인한다."""
import json

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from projects.chapter06_kb_dashboard.dashboard import axis_controls


@pytest.mark.parametrize("values,unit,baseline", [
    ([-20., 5., np.nan, np.inf], "%", None),
    ([100., 100.], "지수", 100.),
    ([0., 1.], "건", None),
    ([np.nan], "%", None),
])
def test_bounds_are_finite_and_include_values_and_baseline(values, unit, baseline):
    lower, upper, step = axis_controls.value_bounds(values, unit, baseline)
    assert np.isfinite([lower, upper, step]).all()
    assert lower < upper
    assert step > 0
    for value in values + ([baseline] if baseline is not None else []):
        if np.isfinite(value):
            assert lower <= value <= upper
    if unit == "건":
        assert step == 1


def test_axis_controls_keep_rebased_values_when_view_is_zoomed(monkeypatch):
    monkeypatch.setattr(axis_controls, "vertical_range", lambda *args, **kwargs: (105., 115.))
    app = AppTest.from_string('''
import pandas as pd
import streamlit as st
from projects.chapter06_kb_dashboard.dashboard.charts import create_line_chart
from projects.chapter06_kb_dashboard.dashboard.axis_controls import render_axis_controls
df = pd.DataFrame({"날짜": pd.date_range("2020-01-01", periods=3, freq="MS"),
                   "지역명": ["서울"]*3, "값": [100., 110., 120.]})
fig = create_line_chart(df, "비교", "지수", baseline=100.)
start, end = render_axis_controls(fig, df, "지수", "test_index", baseline=100.)
st.json({"start": str(start), "end": str(end), "values": list(fig.data[0].y),
         "y_range": list(fig.layout.yaxis.range), "baseline": fig.layout.shapes[0].y0})
''').run()
    assert not app.exception
    options = app.select_slider[0].options
    assert options == ["2020-01", "2020-02", "2020-03"]
    import pandas as pd
    app.select_slider[0].set_value((pd.Timestamp("2020-02-01"), pd.Timestamp("2020-03-01"))).run()
    assert not app.exception
    result = json.loads(app.json[0].value)
    assert result["start"].startswith("2020-02")
    assert result["values"] == [100., 110., 120.]
    assert result["y_range"] == [105., 115.]
    assert result["baseline"] == 100.
