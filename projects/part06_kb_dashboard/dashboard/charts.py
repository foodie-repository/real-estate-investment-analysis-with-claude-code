"""
Plotly 선 그래프 + Pandas Styler 히트맵 테이블

시계열 분석 뷰에서 사용하는 차트 생성 모듈이다.
- 선 그래프: 시군구별 지표 추이 비교
- 히트맵 테이블: 행=날짜, 열=시군구, 셀=값 (색상 그라데이션)
"""
import pandas as pd
import plotly.graph_objects as go



def create_line_chart(
    df: pd.DataFrame,
    title: str,
    unit: str = "%",
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
        group_sorted = group.sort_values("날짜")
        fig.add_trace(go.Scatter(
            x=group_sorted["날짜"],
            y=group_sorted["값"],
            mode="lines",
            name=str(name),
            hovertemplate=f"%{{x|%Y-%m}}<br>{name}: %{{y:.1f}}{unit}<extra></extra>",
            line=dict(width=1.8),
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        xaxis=dict(
            title="",
            tickformat="%Y-%m",
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

    return fig


def create_heatmap_table(
    df: pd.DataFrame,
    unit: str = "%",
):
    """
    시계열 데이터를 히트맵 테이블로 변환한다.
    행=시군구명, 열=날짜(연-월), 셀=값.
    모든 지표에 RdBu_r(파랑↔흰색↔빨강) 색상을 사용한다.

    Args:
        df: DataFrame(날짜, sig_cd, 지역명, 값)
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

    # Diverging 색상: 파랑(약) ↔ 흰색(중간) ↔ 빨강(강)
    cmap = "RdBu_r"
    data_min = pivot.min().min()
    if data_min < 0:
        # 증감률: 0 기준 대칭
        abs_max = pivot.abs().max().max()
        vmin, vmax = -abs_max, abs_max
    else:
        # 전세가율·거래량: 중앙값 기준 대칭
        median_val = pivot.stack().median()
        abs_max = max(abs(data_min - median_val), abs(pivot.max().max() - median_val))
        vmin, vmax = median_val - abs_max, median_val + abs_max

    # 포맷 설정
    if unit == "건":
        fmt = "{:.0f}"
    else:
        fmt = "{:.1f}"

    styled = (
        pivot.style
        .background_gradient(cmap=cmap, vmin=vmin, vmax=vmax, axis=None)
        .format(fmt, na_rep="-")
    )

    return styled
