"""
Plotly 선 그래프 + Pandas Styler 히트맵 테이블

시계열 분석 뷰에서 사용하는 차트 생성 모듈이다.
- 선 그래프: 시군구별 지표 추이 비교
- 히트맵 테이블: 행=날짜, 열=시군구, 셀=값 (색상 그라데이션)
"""
import pandas as pd
import plotly.graph_objects as go

from projects.chapter06_kb_dashboard.dashboard.choropleth import get_color_scale_bounds


def create_line_chart(
    df: pd.DataFrame,
    title: str,
    unit: str = "%",
    baseline: float | None = None,
) -> go.Figure:
    """
    시군구별 시계열 선 그래프를 생성한다.

    Args:
        df: DataFrame(날짜, sig_cd, 지역명, 값)
        title: 차트 제목
        unit: 단위 (예: "%", "건")

    Returns:
        plotly Figure 객체
    """
    fig = go.Figure()

    if df.empty:
        fig.update_layout(title=title)
        return fig

    # 시군구별로 선 추가
    for name, group in df.groupby("지역명"):
        months = pd.date_range(df["날짜"].min(), df["날짜"].max(), freq="MS")
        group_sorted = group.set_index("날짜").reindex(months).rename_axis("날짜").reset_index()
        fig.add_trace(go.Scatter(
            x=group_sorted["날짜"],
            y=group_sorted["값"],
            mode="lines",
            connectgaps=False,
            name=str(name),
            hovertemplate=f"{name}: %{{y:.1f}}{'' if unit.strip() == '지수' else unit}<extra></extra>",
            line=dict(width=1.8),
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        xaxis=dict(
            title="",
            tickformat="%Y-%m",
            hoverformat="%Y-%m",
            dtick="M6",
            gridcolor="#f0f0f0",
            showline=True,
            linecolor="#ccc",
        ),
        yaxis=dict(
            title=f"값 ({unit})",
            gridcolor="#f0f0f0",
            zeroline=True,
            zerolinecolor="#bbb",
            zerolinewidth=1,
        ),
        hovermode="x unified",
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.02,
            font=dict(size=11),
        ),
        height=500,
        margin=dict(l=50, r=120, t=50, b=40),
        plot_bgcolor="white",
    )

    if baseline is not None:
        fig.add_hline(y=baseline, line_dash="dot", line_color="#999", line_width=1)
        fig.update_yaxes(title="시작 시점 = 100")
    return fig


def create_heatmap_table(
    df: pd.DataFrame,
    center_mode: str,
    unit: str = "%",
):
    """
    시계열 데이터를 히트맵 테이블로 변환한다.
    행=시군구명, 열=날짜(연-월), 셀=값.
    모든 지표에 RdBu_r(파랑↔흰색↔빨강) 색상을 사용한다.

    Args:
        df: DataFrame(날짜, sig_cd, 지역명, 값)
        center_mode: 색상 중심 모드 (yoy는 0, direct/count는 중앙값)
        unit: 단위

    Returns:
        Pandas Styler 객체 (Streamlit st.dataframe에 전달)
    """
    if df.empty:
        return pd.DataFrame().style

    # 피벗: 행=지역명, 열=날짜 (Tableau 스타일 — 지역 비교에 직관적)
    pivot = df.pivot_table(
        index="지역명",
        columns="날짜",
        values="값",
        aggfunc="first",
    )
    pivot.columns = pivot.columns.strftime("%Y-%m")
    pivot = pivot[sorted(pivot.columns)]  # 날짜 오름차순 (왼→오)

    # 포맷 설정
    if unit == "건":
        fmt = "{:.0f}"
    else:
        fmt = "{:.1f}"

    styled = pivot.style.format(fmt, na_rep="-")
    values = pivot.stack(future_stack=True)
    color_bounds = get_color_scale_bounds(values - 100 if center_mode == "index" else values,
                                         "yoy" if center_mode == "index" else center_mode)
    if color_bounds is not None and center_mode == "index":
        color_bounds = tuple(value + 100 for value in color_bounds)
    if color_bounds is not None:
        styled = styled.background_gradient(
            cmap="RdBu_r",
            vmin=color_bounds[0],
            vmax=color_bounds[1],
            axis=None,
        )

    return styled
