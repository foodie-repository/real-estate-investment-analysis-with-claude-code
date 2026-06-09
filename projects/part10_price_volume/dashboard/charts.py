"""
차트 생성 모듈

Plotly로 가격·거래량 차트를 생성한다.
태블로 레퍼런스 이미지 기준:
  매매 가격 → 전세 가격 → 매매 거래량 → 전세 거래량 (4행 분리)
"""
from datetime import datetime, timedelta

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from projects.part10_price_volume.dashboard.constants import (
    COLOR_매매, COLOR_매매_BAR,
    COLOR_전세, COLOR_전세_BAR,
    COLOR_평형대,
    평형대_목록,
)


def _ym_to_date(ym: int) -> datetime:
    """계약년월(정수)를 datetime으로 변환한다 (15일 기준)."""
    return datetime(ym // 100, ym % 100, 15)


def _ym_to_str(ym: int) -> str:
    """계약년월(정수)를 'YYYY-MM' 문자열로 변환한다."""
    return f"{ym // 100}-{ym % 100:02d}"


def _add_jitter(df):
    """산점도용 jitter를 추가한다. 같은 월의 점들이 수평으로 퍼진다."""
    df = df.copy()
    dates = df["계약년월"].apply(_ym_to_date)
    rng = np.random.default_rng(seed=42)
    jitter = rng.uniform(-12, 12, size=len(df))
    df["날짜"] = [d + timedelta(days=j) for d, j in zip(dates, jitter)]
    return df


def _build_figure(types_present: list[str]) -> tuple[go.Figure, dict]:
    """
    표시할 거래유형에 따라 적절한 subplot 구조를 생성한다.

    Returns:
        (figure, row_map) — row_map은 {"매매_가격": 1, "전세_가격": 2, ...} 형태
    """
    rows = []
    row_map = {}
    heights = []

    for t in types_present:
        row_map[f"{t}_가격"] = len(rows) + 1
        rows.append(f"{t} 가격 (억 원)")
        heights.append(0.35)

    for t in types_present:
        row_map[f"{t}_거래량"] = len(rows) + 1
        rows.append(f"{t} 거래량 (건)")
        heights.append(0.15)

    fig = make_subplots(
        rows=len(rows), cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=heights,
    )

    # 각 subplot에 연한 회색 테두리 + 안쪽 상단 제목
    _border = dict(showline=True, linewidth=1, linecolor="#D0D0D0", mirror=True)
    for i, title in enumerate(rows, 1):
        fig.update_xaxes(_border, row=i, col=1)
        fig.update_yaxes(_border, row=i, col=1)
        # yaxis 도메인 상단에 제목 배치
        y_domain = fig.get_subplot(i, 1).yaxis.domain
        fig.add_annotation(
            text=f"<b>{title}</b>",
            xref="paper", yref="paper",
            x=0.5, y=y_domain[1] - 0.005,
            xanchor="center", yanchor="top",
            showarrow=False,
            font=dict(size=13, color="#555"),
        )

    return fig, row_map


def create_scatter_chart(data: dict, height: int = 800) -> go.Figure:
    """
    개별 실거래가 산점도 (평형대별 색상, jitter 적용)
    + 거래량 막대 — 매매/전세 각각 분리 행 배치
    """
    types_present = [t for t in ("매매", "전세") if t in data and not data[t].empty]
    if not types_present:
        return go.Figure()

    fig, row_map = _build_figure(types_present)

    bar_colors = {"매매": COLOR_매매_BAR, "전세": COLOR_전세_BAR}

    for 유형 in types_present:
        df = _add_jitter(data[유형])
        price_row = row_map[f"{유형}_가격"]
        vol_row = row_map[f"{유형}_거래량"]

        # 산점도: 평형대별 색상 구분 (범례 순서 고정)
        for 평형 in 평형대_목록:
            subset = df[df["평형대"] == 평형]
            if subset.empty:
                continue
            color = COLOR_평형대.get(평형, "#999999")

            fig.add_trace(
                go.Scatter(
                    x=subset["날짜"],
                    y=subset["가격_억"],
                    mode="markers",
                    name=평형,
                    marker=dict(color=color, size=4, opacity=0.6),
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "계약년월: %{customdata[5]}<br>"
                        "가격: %{y}억<br>"
                        "면적: %{customdata[1]}㎡ (%{customdata[3]}평)<br>"
                        "층: %{customdata[2]}<br>"
                        "평형대: %{customdata[4]}<extra></extra>"
                    ),
                    customdata=subset[["단지명", "전용면적", "층", "추정평형", "평형대", "계약년월"]].values,
                    legendgroup=평형,
                    showlegend=(유형 == types_present[0]),
                ),
                row=price_row, col=1,
            )

        # 거래량 막대
        df["월"] = df["계약년월"].apply(_ym_to_str)
        monthly = df.groupby("월").size().reset_index(name="거래량")
        fig.add_trace(
            go.Bar(
                x=monthly["월"],
                y=monthly["거래량"],
                name=f"{유형} 거래량",
                marker_color=bar_colors[유형],
                opacity=0.8,
                hovertemplate="%{x}<br>거래량: %{y}건<extra></extra>",
                showlegend=False,
            ),
            row=vol_row, col=1,
        )

    fig.update_layout(
        height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=50, t=60, b=50),
        hovermode="closest",
    )

    return fig


def create_line_chart(data: dict, height: int = 800) -> go.Figure:
    """
    월별 중위가 선 그래프 + 거래량 막대
    매매/전세 각각 분리 행 배치
    """
    types_present = [t for t in ("매매", "전세") if t in data and not data[t].empty]
    if not types_present:
        return go.Figure()

    fig, row_map = _build_figure(types_present)

    line_colors = {"매매": COLOR_매매, "전세": COLOR_전세}
    bar_colors = {"매매": COLOR_매매_BAR, "전세": COLOR_전세_BAR}

    for 유형 in types_present:
        df = data[유형].copy()
        df["날짜"] = df["계약년월"].apply(_ym_to_str)
        price_row = row_map[f"{유형}_가격"]
        vol_row = row_map[f"{유형}_거래량"]

        # 선 그래프: 월별 중위가
        fig.add_trace(
            go.Scatter(
                x=df["날짜"],
                y=df["중위가_억"],
                mode="lines+markers",
                name=f"{유형} 중위가",
                line=dict(color=line_colors[유형], width=2),
                marker=dict(size=4),
                hovertemplate="%{x}<br>중위가: %{y}억<extra></extra>",
            ),
            row=price_row, col=1,
        )

        # 거래량 막대
        fig.add_trace(
            go.Bar(
                x=df["날짜"],
                y=df["거래량"],
                name=f"{유형} 거래량",
                marker_color=bar_colors[유형],
                opacity=0.8,
                hovertemplate="%{x}<br>거래량: %{y}건<extra></extra>",
                showlegend=False,
            ),
            row=vol_row, col=1,
        )

    fig.update_layout(
        height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=50, t=60, b=50),
        hovermode="x unified",
    )

    return fig
