"""가격·거래량 차트의 공통 기간과 행별 Y축 표시 범위."""
import pandas as pd
import streamlit as st

from projects.chapter06_kb_dashboard.dashboard.axis_controls import value_bounds
from projects.chapter07_price_gap_table.dashboard.vertical_slider import vertical_range
from projects.chapter09_price_volume.dashboard.render import render_chart
from projects.chapter09_price_volume.dashboard.charts import _set_volume_axis, set_date_ticks, volume_totals


def render_axis_controls(fig, key):
    layout_key = f"price_{key}"
    st.html('''<style>
    .st-key-price_monthly_layout [data-testid="stHorizontalBlock"] {
        gap: 4px; flex-wrap: nowrap;
    }
    .st-key-price_monthly_layout [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
        flex: 0 0 48px; width: 48px; min-width: 48px;
    }
    .st-key-price_monthly_layout [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
        flex: 1 1 0; min-width: 0;
    }
    .st-key-price_monthly_y { gap: 0; }
    .st-key-price_monthly_y iframe { display: block; }
    .st-key-price_monthly_layout [data-baseweb="slider"] { filter: grayscale(1); }
    .st-key-price_monthly_layout [data-baseweb="slider"] div:has(> [role="slider"]) + div { opacity: 0.5; }
    .st-key-price_monthly_layout [role="slider"] { background-color: #b8b8b8; }
    </style>'''.replace("price_monthly", layout_key))
    layout = st.container(key=f"{layout_key}_layout")
    side, main = layout.columns([1, 9], gap="small")
    height = int(fig.layout.height)
    top, bottom = int(fig.layout.margin.t), int(fig.layout.margin.b)
    plot_height = height - top - bottom
    rows = len(fig.layout.annotations)
    boundary = 0
    with side, st.container(key=f"{layout_key}_y"):
        for row in range(1, rows + 1):
            axis = fig.get_subplot(row, 1).yaxis
            axis_id = "y" if row == 1 else f"y{row}"
            traces = [trace for trace in fig.data if trace.yaxis == axis_id]
            volume = traces[0].type == "bar"
            unit = "건" if volume else "지수" if fig.layout.shapes else "억 원"
            lower, upper, step = value_bounds(
                list(volume_totals(traces).values()) if volume else [value for trace in traces for value in trace.y], unit,
                baseline=0 if volume else 100 if fig.layout.shapes else None,
            )
            if volume:
                lower = 0.
            plot_top = round(top + (1 - axis.domain[1]) * plot_height)
            plot_bottom = round(top + (1 - axis.domain[0]) * plot_height)
            end = height if row == rows else plot_bottom + 24
            selected = vertical_range(
                lower, upper, step, unit, f"{key}_{axis_id}_range",
                end - boundary, top=plot_top - boundary, bottom=end - plot_bottom,
            )
            axis.update(range=selected, autorange=False)
            if volume:
                _set_volume_axis(fig, row, selected[1] - selected[0])
            boundary = end
    dates = sorted({pd.Timestamp(date) for trace in fig.data for date in trace.x if date is not None})
    months = list(pd.date_range(dates[0], dates[-1], freq="MS"))
    with main:
        chart = st.container()
        if len(months) > 1:
            start, end = st.select_slider(
                "X축 범위 · 기간", options=months, value=(months[0], months[-1]),
                format_func=lambda date: date.strftime("%Y-%m"), key=f"{key}_x_range",
            )
        else:
            start = end = months[0]
            st.caption(f"표시 기간: {start:%Y-%m}")
        # 산점도는 월말까지의 점을 포함하고, 월 중앙의 거래량 막대도 보존한다.
        scatter = any(trace.type == "scatter" and trace.mode == "markers" for trace in fig.data)
        bounds = ([start, end + pd.offsets.MonthBegin(1)] if scatter else
                  [start - pd.Timedelta(days=15), end + pd.Timedelta(days=15)])
        fig.update_xaxes(range=bounds, autorange=False)
        set_date_ticks(fig, start, end)
        with chart:
            render_chart(fig)
