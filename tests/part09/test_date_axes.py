"""각 행에서 날짜를 읽고 기간 확대 후 더 세밀한 눈금으로 비교할 수 있다."""
import pandas as pd

from projects.chapter09_price_volume.dashboard.charts import create_line_chart


def test_every_monthly_row_shows_dates_for_long_comparison():
    data = {kind: pd.DataFrame({
        "계약년월": [201101, 202601], "비교대상": ["테스트 · 30평대"] * 2,
        "중위가_억": values, "거래량": [2, 3],
    }) for kind, values in [("매매", [10., 20.]), ("전세", [5., 8.])]}
    fig = create_line_chart(data)
    for axis in fig.select_xaxes():
        assert axis.showticklabels is True
        assert axis.tickformat == "%Y-%m"
        assert axis.dtick == "M12"


def test_thirteen_calendar_months_use_quarterly_ticks():
    data = {"매매": pd.DataFrame({
        "계약년월": [202501, 202601], "비교대상": ["테스트"] * 2,
        "중위가_억": [10., 12.], "거래량": [2, 3],
    })}
    fig = create_line_chart(data)
    assert all(axis.dtick == "M3" for axis in fig.select_xaxes())
