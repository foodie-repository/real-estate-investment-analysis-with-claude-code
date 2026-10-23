"""KB 시계열 차트의 표시 범위를 조절하는 슬라이더."""
from math import ceil, floor

import numpy as np
import pandas as pd
import streamlit as st

from projects.chapter07_price_gap_table.dashboard.vertical_slider import vertical_range


def value_bounds(values, unit, baseline=None):
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if baseline is not None:
        finite = np.append(finite, baseline)
    if not len(finite):
        return 0., 1., 1. if unit == "건" else 0.01
    low, high = float(finite.min()), float(finite.max())
    step = 1. if unit == "건" else 0.01
    padding = max((high - low) * 0.05, abs(low) * 0.01, step)
    return round(floor((low - padding) / step) * step, 2), round(ceil((high + padding) / step) * step, 2), step


def render_axis_controls(fig, df, unit, key, baseline=None):
    """계산된 값은 유지하고 축 표시 범위와 히트맵용 기간을 반환한다."""
    st.html('''<style>
    .st-key-kb_ts_layout [data-testid="stHorizontalBlock"] {
        gap: 4px; flex-wrap: nowrap;
    }
    .st-key-kb_ts_layout [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
        flex: 0 0 48px; width: 48px; min-width: 48px;
    }
    .st-key-kb_ts_layout [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
        flex: 1 1 0; min-width: 0;
    }
    .st-key-kb_ts_layout [data-baseweb="slider"] { filter: grayscale(1); }
    .st-key-kb_ts_layout [data-baseweb="slider"] div:has(> [role="slider"]) + div { opacity: 0.5; }
    .st-key-kb_ts_layout [role="slider"] { background-color: #b8b8b8; }
    </style>''')
    # 긴 기간의 세로 날짜 레이블과 세로 슬라이더의 아래 끝을 맞춘다.
    fig.update_layout(margin=dict(b=100))
    dates = list(pd.date_range(df["날짜"].min(), df["날짜"].max(), freq="MS"))
    lower, upper, step = value_bounds(df["값"], unit, baseline)
    layout = st.container(key="kb_ts_layout")
    side, main = layout.columns([1, 9], gap="small")
    with side:
        selected = vertical_range(
            lower, upper, step, unit, f"{key}_y_range", int(fig.layout.height),
            top=int(fig.layout.margin.t), bottom=int(fig.layout.margin.b),
        )
    fig.update_yaxes(range=selected, autorange=False)
    with main:
        chart = st.container()
        if len(dates) > 1:
            start, end = st.select_slider(
                "X축 범위 · 기간", options=dates, value=(dates[0], dates[-1]),
                format_func=lambda date: date.strftime("%Y-%m"), key=f"{key}_x_range",
            )
        else:
            start = end = dates[0]
            st.caption(f"표시 기간: {start:%Y-%m}")
        # 한 달만 선택해도 축 폭을 확보한다.
        display_range = [start, end] if start != end else [
            start - pd.Timedelta(days=15), end + pd.Timedelta(days=15),
        ]
        fig.update_xaxes(range=display_range, autorange=False)
        chart.plotly_chart(fig, use_container_width=True, key=f"{key}_chart")
    return start, end
