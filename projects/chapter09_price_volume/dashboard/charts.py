"""
차트 생성 모듈

Plotly로 가격·거래량 차트를 생성한다.
태블로 레퍼런스 이미지 기준:
  매매 가격 → 전세 가격 → 매매 거래량 → 전세 거래량 (4행 분리)
"""
from datetime import datetime, timedelta
import math
from collections import Counter, defaultdict

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.colors import qualitative
from plotly.subplots import make_subplots
from src.utils.address import parse_sigungu

from projects.chapter09_price_volume.dashboard.preprocessing import prepare_monthly_comparison

from projects.chapter09_price_volume.dashboard.constants import (
    COLOR_매매, COLOR_전세,
    COLOR_평형대,
)


def _ym_to_date(ym: int) -> datetime:
    """계약년월(정수)를 datetime으로 변환한다 (15일 기준)."""
    return datetime(ym // 100, ym % 100, 15)


def _ym_to_str(ym: int) -> str:
    """계약년월(정수)를 'YYYY-MM' 문자열로 변환한다."""
    return f"{ym // 100}-{ym % 100:02d}"


def _add_jitter(df):
    """산점도용 jitter를 추가한다. 같은 월의 점들이 수평으로 퍼진다."""
    # 범위 슬라이더의 재조회에서 같은 달의 반환 순서가 바뀌어도 점 위치를 유지한다.
    columns = ["계약년월", "비교대상", "단지명", "평형대", "전용면적", "가격_억", "층", "추정평형"]
    df = df.sort_values([column for column in columns if column in df], kind="stable")
    dates = df["계약년월"].apply(_ym_to_date)
    rng = np.random.default_rng(seed=42)
    jitter = rng.uniform(-12, 12, size=len(df))
    df["날짜"] = [d + timedelta(days=j) for d, j in zip(dates, jitter)]
    return df


def _build_figure(types_present: list[str], vertical_spacing: float = 0.04) -> tuple[go.Figure, dict]:
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
        vertical_spacing=vertical_spacing,
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


def set_date_ticks(fig: go.Figure, start=None, end=None):
    """공유 축이어도 각 행에 날짜를 표시하고 조회 기간에 맞춰 간격을 조절한다."""
    if start is None or end is None:
        dates = (str(value)[:10] for trace in fig.data for value in trace.x if value is not None)
        first_date = next(dates, None)
        if first_date is None:
            return
        start = end = first_date
        for value in dates:
            start, end = min(start, value), max(end, value)
    first, last = str(start), str(end)
    months = (int(last[:4]) - int(first[:4])) * 12 + int(last[5:7]) - int(first[5:7]) + 1
    interval = 1 if months <= 12 else 3 if months <= 36 else 6 if months <= 84 else 12 if months <= 240 else 24
    fig.update_xaxes(type="date", showticklabels=True, tickformat="%Y-%m",
                     hoverformat="%Y-%m", dtick=f"M{interval}", tickangle=0,
                     tickfont=dict(size=10), ticks="outside", ticklen=3)


def _comparison_styles(data: dict) -> tuple[dict, dict]:
    """두 탭에서 같은 비교 대상에 같은 색과 중복 없는 범례 이름을 부여한다."""
    labels = sorted({label for df in data.values() if not df.empty
                     for label in df["비교대상" if "비교대상" in df else "평형대"]})
    palette = qualitative.Plotly + qualitative.Dark24
    colors = {label: COLOR_평형대.get(label, palette[i % len(palette)]) for i, label in enumerate(labels)}
    parts = {label: label.rsplit(" (", 1) for label in labels}
    addresses = defaultdict(set)
    for base, *address in parts.values():
        if address:
            addresses[base.rsplit(" · ", 1)[0]].add(address[0])
    names = {}
    for label, (base, *address) in parts.items():
        name = base
        if address and len(addresses[base.rsplit(" · ", 1)[0]]) > 1:
            region = address[0].split(" 지번 ", 1)[0].split(" 도로명 ", 1)[0]
            dong = parse_sigungu(region)["읍면동"]
            name = f"{base} ({dong or region})"
        names[label] = name
    # 읍면동까지 같아도 서로 다른 주소의 단지를 합치지 않는다.
    counts = Counter(names.values())
    names = {label: label if counts[name] > 1 else name for label, name in names.items()}
    return colors, names


VOLUME_HOVER = "%{x|%Y-%m}<br>%{fullData.name}<br>거래량: %{y:,.0f}건<extra></extra>"


def volume_totals(traces):
    """하나의 거래량 축에 쌓이는 월별 건수 합계."""
    totals = defaultdict(int)
    for trace in traces:
        if trace.type == "bar" and trace.visible not in (False, "legendonly"):
            for month, count in zip(trace.x, trace.y):
                totals[month] += int(count)
    return totals


def create_scatter_chart(data: dict, height: int = 800) -> go.Figure:
    """
    개별 실거래가 산점도 (선택 단지·평형별 색상, jitter 적용)
    + 거래량 막대 — 매매/전세 각각 분리 행 배치
    """
    types_present = [t for t in ("매매", "전세") if t in data and not data[t].empty]
    if not types_present:
        return go.Figure()

    fig, row_map = _build_figure(types_present, vertical_spacing=0.10)

    colors, names = _comparison_styles(data)
    shown = set()

    for 유형 in types_present:
        df = _add_jitter(data[유형])
        price_row = row_map[f"{유형}_가격"]
        vol_row = row_map[f"{유형}_거래량"]

        group_column = "비교대상" if "비교대상" in df else "평형대"
        for label, subset in df.groupby(group_column, sort=True):

            fig.add_trace(
                go.Scatter(
                    x=subset["날짜"],
                    y=subset["가격_억"],
                    mode="markers",
                    name=names[label],
                    marker=dict(color=colors[label], size=4, opacity=0.6),
                    hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#D1D5DB",
                                    font=dict(color="#31333F")),
                    hovertemplate=(
                        f"<span style='color:{colors[label]}'>●</span> "
                        "<b>%{customdata[0]} · %{customdata[4]}</b><br>"
                        "계약년월: %{customdata[5]}<br>"
                        "가격: %{y}억<br>"
                        "면적: %{customdata[1]}㎡ (%{customdata[3]}평)<br>"
                        "층: %{customdata[2]}<extra></extra>"
                    ),
                    customdata=subset[["단지명", "전용면적", "층", "추정평형", "평형대", "계약년월"]].values,
                    legendgroup=label,
                    showlegend=label not in shown,
                ),
                row=price_row, col=1,
            )
            shown.add(label)

        # 빈 달은 0건으로 채우고 같은 월에 단지·평형별 건수를 쌓는다.
        months = [int(month.strftime("%Y%m")) for month in pd.date_range(
            _ym_to_date(int(df["계약년월"].min())).replace(day=1),
            _ym_to_date(int(df["계약년월"].max())).replace(day=1), freq="MS")]
        for label, subset in df.groupby(group_column, sort=True):
            counts = subset.groupby("계약년월").size().reindex(months, fill_value=0)
            fig.add_trace(go.Bar(
                x=[_ym_to_str(month) for month in months], y=counts.tolist(),
                xperiod="M1", xperiodalignment="middle",
                name=names[label], legendgroup=label, marker_color=colors[label],
                opacity=0.65,
                hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#D1D5DB",
                                font=dict(color="#31333F")),
                hovertemplate=VOLUME_HOVER.replace(
                    "%{fullData.name}",
                    f"<span style='color:{colors[label]}'>●</span> %{{fullData.name}}",
                ),
                showlegend=False,
            ), row=vol_row, col=1)
        _set_volume_axis(fig, vol_row, int(df.groupby("계약년월").size().max()))

    fig.update_layout(
        height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=50, t=60, b=50),
        hovermode="closest",
        barmode="stack",
    )

    set_date_ticks(fig)
    return fig


def _set_volume_axis(fig: go.Figure, row: int, maximum: int):
    """거래량 축은 0부터 읽기 쉬운 정수 간격으로 표시한다."""
    target = max(1, maximum / 5)
    magnitude = 10 ** math.floor(math.log10(target))
    step = next(m * magnitude for m in (1, 2, 5, 10) if m * magnitude >= target)
    fig.update_yaxes(tickformat=",d", tick0=0, dtick=step, rangemode="tozero", row=row, col=1)


def create_line_chart(data: dict, height: int = 800, base_month: int | None = None) -> go.Figure:
    """
    단지·평형별 월별 중위가 또는 기준월=100 선 + 같은 대상의 거래량 막대.
    매매/전세 각각 분리 행 배치. 거래 없는 내부 구간만 점선으로 연결한다.
    """
    # 기준월에 거래가 없어 일부 대상이 빠져도 다른 대상의 색은 유지한다.
    colors, names = _comparison_styles(data)
    data, excluded = prepare_monthly_comparison(data, base_month)
    types_present = [t for t in ("매매", "전세") if t in data and not data[t].empty]
    if not types_present:
        return go.Figure(layout=dict(meta={"excluded": excluded}))

    # 각 행의 세로 슬라이더 숫자와 다음 행의 제목이 겹치지 않도록 여백을 둔다.
    fig, row_map = _build_figure(types_present, vertical_spacing=0.10)
    shown = set()

    for 유형 in types_present:
        price_row = row_map[f"{유형}_가격"]
        vol_row = row_map[f"{유형}_거래량"]
        _set_volume_axis(fig, vol_row, int(data[유형].groupby("계약년월")["거래량"].sum().max()))
        if base_month is not None:
            fig.layout.annotations[price_row - 1].text = f"<b>{유형} 가격 (기준월 = 100)</b>"
            fig.add_hline(y=100, line_dash="dot", line_color="#999", row=price_row, col=1,
                          exclude_empty_subplots=False)
        for label, df in data[유형].groupby("비교대상", sort=True):
            display_name = names[label]
            dates = df["계약년월"].apply(_ym_to_str)
            hover = (
                "%{x|%Y-%m}<br>기준월 대비 지수: %{y:.2f}<br>변화율: %{customdata[2]:.2f}%"
                if base_month is not None else "%{x|%Y-%m}"
            ) + "<br>중위가: %{customdata[0]:.2f}억<br>거래량: %{customdata[1]:.0f}건<extra>%{fullData.name}</extra>"
            customdata = np.column_stack([df["중위가_억"], df["거래량"], df["표시값"] - 100])
            valid = np.flatnonzero(np.isfinite(df["표시값"].to_numpy()))
            gap_x, gap_y = [], []
            # 최종 집계의 결측 구간 양 끝만 점선으로 잇는다. 월별 가격은 생성하지 않는다.
            for left, right in zip(valid[:-1], valid[1:]):
                if right - left > 1:
                    gap_x.extend([dates.iloc[left], dates.iloc[right], None])
                    gap_y.extend([df["표시값"].iloc[left], df["표시값"].iloc[right], None])
            if gap_x:
                fig.add_trace(go.Scatter(
                    x=gap_x, y=gap_y, mode="lines", connectgaps=False,
                    name=f"{display_name} · 거래 없는 기간", legendgroup=label, showlegend=False,
                    line=dict(color=colors[label], width=2, dash="dot"), hoverinfo="skip",
                ), row=price_row, col=1)
            fig.add_trace(
                go.Scatter(
                    x=dates, y=df["표시값"], mode="lines+markers", connectgaps=False,
                    name=display_name, legendgroup=label, showlegend=label not in shown,
                    line=dict(color=colors[label], width=2), marker=dict(size=4),
                    customdata=customdata, hovertemplate=hover,
                ), row=price_row, col=1,
            )
            shown.add(label)
            fig.add_trace(
                go.Bar(
                    x=dates.tolist(), y=df["거래량"].tolist(), name=display_name, legendgroup=label,
                    marker_color=colors[label], opacity=0.65,
                    hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#D1D5DB",
                                    font=dict(color="#31333F")),
                    hovertemplate=VOLUME_HOVER,
                    showlegend=False,
                ), row=vol_row, col=1,
            )
        fig.update_xaxes(type="date", tickformat="%Y-%m", hoverformat="%Y-%m", row=price_row, col=1)
        fig.update_xaxes(type="date", tickformat="%Y-%m", hoverformat="%Y-%m", row=vol_row, col=1)

    fig.update_layout(
        height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=50, r=50, t=60, b=50),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#D1D5DB",
                        font=dict(color="#31333F")),
        barmode="stack",
        meta={"excluded": excluded},
    )

    set_date_ticks(fig)
    return fig
