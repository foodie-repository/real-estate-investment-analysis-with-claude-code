"""
Part10 가격·거래량 대시보드

실행: uv run streamlit run projects/part10_price_volume/dashboard/app.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (어디서든 실행 가능하도록)
_ROOT = str(Path(__file__).resolve().parents[3])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st

from projects.part10_price_volume.dashboard.constants import 평형대_목록
from projects.part10_price_volume.dashboard.preprocessing import (
    get_region_options,
    get_date_range,
    get_individual_trades,
    get_monthly_summary,
    get_summary_stats,
)
from projects.part10_price_volume.dashboard.charts import (
    create_scatter_chart,
    create_line_chart,
)


# =============================================================================
# 페이지 설정
# =============================================================================
st.set_page_config(
    page_title="가격·거래량 대시보드",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏠 아파트 가격·거래량 대시보드")


# =============================================================================
# 데이터 캐싱
# =============================================================================
@st.cache_data(ttl=3600)
def load_region_options():
    return get_region_options()


@st.cache_data(ttl=3600)
def load_date_range():
    return get_date_range()


# =============================================================================
# 사이드바
# =============================================================================
with st.sidebar:
    st.header("필터")

    # 지역 선택 (계층적)
    region_data = load_region_options()

    시도_목록 = sorted(region_data.keys())
    선택_시도 = st.selectbox("시도", 시도_목록, index=시도_목록.index("서울특별시") if "서울특별시" in 시도_목록 else 0)

    시군구_목록 = sorted(region_data.get(선택_시도, {}).keys())
    강남_idx = 시군구_목록.index("강남구") if "강남구" in 시군구_목록 else 0
    선택_시군구 = st.selectbox("시군구", 시군구_목록, index=강남_idx)

    읍면동_목록 = sorted(region_data.get(선택_시도, {}).get(선택_시군구, {}).keys())
    선택_읍면동 = st.multiselect("읍면동", 읍면동_목록, default=[], placeholder="전체")

    # 단지 선택 — 읍면동이 선택된 경우에만 해당 읍면동의 단지 목록
    단지_후보 = []
    if 선택_읍면동:
        for dong in 선택_읍면동:
            단지_후보.extend(region_data.get(선택_시도, {}).get(선택_시군구, {}).get(dong, []))
    else:
        for dong_data in region_data.get(선택_시도, {}).get(선택_시군구, {}).values():
            단지_후보.extend(dong_data)
    단지_후보 = sorted(set(단지_후보))
    선택_단지 = st.multiselect("단지", 단지_후보, default=[], placeholder="전체")

    st.divider()

    # 거래유형
    거래유형 = st.radio("거래유형", ["매매+전세", "매매만", "전세만"], index=0)

    # 평형 필터
    선택_평형대 = st.multiselect("평형대", 평형대_목록, default=["30평대"])

    st.divider()

    # 기간 선택
    min_ym, max_ym = load_date_range()
    min_year = min_ym // 100
    max_year = max_ym // 100

    # 기본값: 전체 기간
    시작년, 종료년 = st.slider(
        "기간 (연도)",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
    )
    시작년월 = 시작년 * 100 + 1   # 해당 연도 1월
    종료년월 = 종료년 * 100 + 12  # 해당 연도 12월

    st.divider()

    # 직거래 포함 여부
    직거래포함 = st.checkbox("직거래 포함", value=False)


# =============================================================================
# 메인 영역
# =============================================================================
if not 선택_시군구:
    st.info("사이드바에서 시군구를 선택하세요.")
    st.stop()

if not 선택_평형대:
    st.warning("평형대를 하나 이상 선택하세요.")
    st.stop()

# 뷰 전환
tab1, tab2 = st.tabs(["📊 개별 실거래가", "📈 월별 중위가"])

# 공통 파라미터
params = dict(
    시도=선택_시도,
    시군구=선택_시군구,
    읍면동=선택_읍면동 or None,
    단지=선택_단지 or None,
    거래유형=거래유형,
    평형대=선택_평형대 if set(선택_평형대) != set(평형대_목록) else None,
    시작년월=시작년월,
    종료년월=종료년월,
    직거래포함=직거래포함,
)

with tab1:
    with st.spinner("개별 거래 데이터 조회 중..."):
        individual_data = get_individual_trades(**params)

    total = sum(len(df) for df in individual_data.values())
    if total == 0:
        st.warning("선택한 조건에 해당하는 거래가 없습니다.")
    else:
        fig = create_scatter_chart(individual_data)
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    with st.spinner("월별 집계 데이터 조회 중..."):
        monthly_data = get_monthly_summary(**params)

    total = sum(len(df) for df in monthly_data.values())
    if total == 0:
        st.warning("선택한 조건에 해당하는 거래가 없습니다.")
    else:
        fig = create_line_chart(monthly_data)
        st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# 요약 정보
# =============================================================================
st.divider()
st.subheader("📋 요약 정보")

if 거래유형 != "전세만":
    with st.spinner("요약 통계 조회 중..."):
        stats = get_summary_stats(
            시도=선택_시도,
            시군구=선택_시군구,
            읍면동=선택_읍면동 or None,
            단지=선택_단지 or None,
            평형대=선택_평형대 if set(선택_평형대) != set(평형대_목록) else None,
            시작년월=시작년월,
            종료년월=종료년월,
            직거래포함=직거래포함,
        )

    col1, col2, col3 = st.columns(3)
    col1.metric("총 거래 건수", f"{stats['총거래건수']:,}건")
    col2.metric("기간 내 최고가", f"{stats['최고가_억']}억")
    col3.metric("기간 내 최저가", f"{stats['최저가_억']}억")

    if not stats["최근거래"].empty:
        st.caption("최근 거래 (최대 3건)")
        recent = stats["최근거래"].copy()
        recent.columns = ["계약년월", "단지명", "전용면적(㎡)", "가격(억)", "층"]
        st.dataframe(recent, use_container_width=True, hide_index=True)
else:
    st.info("매매 요약 정보는 '매매만' 또는 '매매+전세' 모드에서 표시됩니다.")
