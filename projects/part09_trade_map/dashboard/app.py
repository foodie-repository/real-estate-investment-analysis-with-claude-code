"""
아파트 거래량 랭킹 지도 - Streamlit 웹 앱

사이드바 필터로 지역/기간/면적대 등을 선택하면
V-World 지도 위에 거래량 또는 회전율 랭킹 원이 표시된다.

실행: uv run streamlit run projects/part09_trade_map/dashboard/app.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (어디서든 실행 가능하도록)
_ROOT = str(Path(__file__).resolve().parents[3])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
from streamlit_folium import st_folium

from projects.part09_trade_map.dashboard.preprocessing import (
    get_region_options, get_year_range, get_max_세대수,
)
from projects.part09_trade_map.dashboard.pivot import generate_pivot_table
from projects.part09_trade_map.dashboard.map_builder import (
    create_ranking_map, aggregate_by_complex,
)
from projects.part09_trade_map.dashboard.constants import (
    면적대_목록, 평형대_목록, 연식_색상,
)


# =============================================================================
# 페이지 설정
# =============================================================================
st.set_page_config(
    page_title="아파트 거래량 랭킹 지도",
    page_icon="🏠",
    layout="wide",
)

# 상단 여백 줄이기
st.markdown(
    """<style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    header { visibility: hidden; }
    </style>""",
    unsafe_allow_html=True,
)

st.title("아파트 거래량 랭킹 지도")


# =============================================================================
# 캐싱
# =============================================================================
@st.cache_data(ttl=3600)
def load_region_options(거래유형: str):
    """시도→시군구→읍면동 계층 데이터를 거래유형별로 캐싱하여 로드한다."""
    return get_region_options(거래유형)


@st.cache_data(ttl=3600)
def load_year_range(거래유형: str):
    """연도 범위를 캐싱하여 로드한다."""
    return get_year_range(거래유형)


# =============================================================================
# 사이드바 필터
# =============================================================================
st.sidebar.header("필터 설정")

# 거래유형
거래유형 = st.sidebar.radio("거래유형", ["매매", "전세", "월세"], horizontal=True)

# 랭킹 기준
랭킹기준 = st.sidebar.radio("랭킹 기준", ["거래량", "회전율"], horizontal=True)

# 랭킹 표시 개수
랭킹개수 = st.sidebar.select_slider(
    "랭킹 표시 개수",
    options=[10, 20, 30, 40, 50],
    value=20,
)

st.sidebar.divider()

# ── 지역 선택 (계층적 multiselect) ──
regions = load_region_options(거래유형)
시도_목록 = sorted(regions.keys())
시도_선택 = st.sidebar.multiselect(
    "시도", 시도_목록, default=["서울특별시"],
)

# 선택된 시도에 해당하는 시군구 목록 통합
# 복수 시도 선택 시 동명 시군구는 "강서구 (서울특별시)" 형태로 병기
def _build_시군구_목록(시도_선택, regions):
    복수선택 = len(시도_선택) > 1
    if not 복수선택:
        시도 = 시도_선택[0]
        return sorted(regions.get(시도, {}).keys())

    이름_카운터 = {}
    for 시도 in 시도_선택:
        for 시군구 in regions.get(시도, {}).keys():
            이름_카운터[시군구] = 이름_카운터.get(시군구, 0) + 1

    목록 = []
    for 시도 in 시도_선택:
        for 시군구 in regions.get(시도, {}).keys():
            if 이름_카운터[시군구] > 1:
                목록.append(f"{시군구} ({시도})")
            else:
                목록.append(시군구)
    return sorted(set(목록))

시군구_전체목록 = _build_시군구_목록(시도_선택, regions) if 시도_선택 else []
시군구_기본 = ["강남구"] if "강남구" in 시군구_전체목록 else []
시군구_선택 = st.sidebar.multiselect(
    "시군구", 시군구_전체목록, default=시군구_기본,
)


def _parse_시군구_항목(항목):
    """병기 형태("강서구 (서울특별시)")에서 (시군구명, 시도명|None)을 반환한다."""
    if 항목.endswith(")") and " (" in 항목:
        idx = 항목.rfind(" (")
        return 항목[:idx], 항목[idx + 2:-1]
    return 항목, None


def _resolve_시도_시군구(시도_선택, 시군구_선택):
    """선택된 시군구 항목을 파싱하여 필터용 (시도 리스트, 시군구 리스트) 쌍을 반환한다."""
    if not 시군구_선택:
        return 시도_선택, None

    시도_set = set()
    시군구_set = set()
    for 항목 in 시군구_선택:
        시군구명, 시도명 = _parse_시군구_항목(항목)
        시군구_set.add(시군구명)
        if 시도명:
            시도_set.add(시도명)
        else:
            시도_set.update(시도_선택)
    return sorted(시도_set), sorted(시군구_set)


# 선택된 시군구에 해당하는 읍면동 목록 통합
def _build_읍면동_목록(시도_선택, 시군구_선택, regions):
    if not 시군구_선택:
        return sorted({
            읍면동
            for 시도 in 시도_선택
            for 시군구 in regions.get(시도, {}).keys()
            for 읍면동 in regions.get(시도, {}).get(시군구, [])
        })

    결과 = set()
    for 항목 in 시군구_선택:
        시군구명, 시도명 = _parse_시군구_항목(항목)
        검색_시도 = [시도명] if 시도명 else 시도_선택
        for 시도 in 검색_시도:
            for 읍면동 in regions.get(시도, {}).get(시군구명, []):
                결과.add(읍면동)
    return sorted(결과)

읍면동_전체목록 = _build_읍면동_목록(시도_선택, 시군구_선택, regions)
읍면동_선택 = st.sidebar.multiselect("읍면동", 읍면동_전체목록)

st.sidebar.divider()

# ── 기간 선택 ──
year_min, year_max = load_year_range(거래유형)

# Session State 초기화
if "year_slider" not in st.session_state:
    st.session_state.year_slider = year_max


def _change_year(delta, min_val, max_val):
    new = st.session_state.year_slider + delta
    st.session_state.year_slider = max(min_val, min(max_val, new))


기간범위_사용 = st.sidebar.checkbox("기간 범위 모드", value=False)

if 기간범위_사용:
    연도_범위 = st.sidebar.slider(
        "기간 (연도)",
        min_value=year_min,
        max_value=year_max,
        value=(year_max - 1, year_max),
    )
    연도_시작, 연도_끝 = 연도_범위
else:
    st.sidebar.slider(
        "기간 (연도)",
        min_value=year_min,
        max_value=year_max,
        key="year_slider",
    )

    col_prev, col_next = st.sidebar.columns(2)
    with col_prev:
        st.button("◀ 이전", use_container_width=True,
                  on_click=_change_year, args=(-1, year_min, year_max))
    with col_next:
        st.button("다음 ▶", use_container_width=True,
                  on_click=_change_year, args=(1, year_min, year_max))

    연도_시작 = st.session_state.year_slider
    연도_끝 = st.session_state.year_slider

st.sidebar.divider()

# ── 면적 필터 ──
면적대 = st.sidebar.multiselect(
    "면적대 (전용면적 구분)",
    면적대_목록,
    default=면적대_목록,
)

평형대 = st.sidebar.multiselect(
    "평형대 (추정평형 구분)",
    평형대_목록,
    default=평형대_목록,
)

st.sidebar.divider()

# ── 세대수 범위 ──
세대수_사용 = st.sidebar.checkbox("세대수 범위 지정", value=False)
세대수_범위 = None
if 세대수_사용:
    col_min, col_max = st.sidebar.columns(2)
    with col_min:
        세대수_min = st.number_input("최소 세대수", min_value=0, value=0, step=1)
    with col_max:
        세대수_max = st.number_input("최대 세대수", min_value=0, value=get_max_세대수(), step=1)
    if 세대수_min > 세대수_max:
        세대수_min, 세대수_max = 세대수_max, 세대수_min
    세대수_범위 = (세대수_min, 세대수_max)

# 지도 스타일
지도스타일 = st.sidebar.selectbox("지도 스타일", ["기본지도", "위성지도", "하이브리드"])


# =============================================================================
# 데이터 조회 및 지도 표시
# =============================================================================
if not 시도_선택:
    st.warning("시도를 1개 이상 선택해주세요.")
    st.stop()

# 필터 요약 캡션
지역_표시 = ", ".join(시도_선택)
if 시군구_선택:
    지역_표시 += " " + ", ".join(시군구_선택)
if 읍면동_선택:
    지역_표시 += " " + ", ".join(읍면동_선택)

if 연도_시작 == 연도_끝:
    기간_표시 = f"{연도_시작}년"
else:
    기간_표시 = f"{연도_시작}~{연도_끝}년"
st.caption(
    f"**{지역_표시}** | {기간_표시} | "
    f"{거래유형} | {랭킹기준} 상위 {랭킹개수}개"
)

# 피벗테이블 생성
_필터_시도, _필터_시군구 = _resolve_시도_시군구(시도_선택, 시군구_선택)
with st.spinner("데이터 조회 중..."):
    df_pivot = generate_pivot_table(
        거래유형=거래유형,
        시도=_필터_시도 if len(_필터_시도) > 1 else _필터_시도[0],
        시군구=_필터_시군구 if _필터_시군구 else None,
        읍면동=읍면동_선택 if 읍면동_선택 else None,
        연도_시작=연도_시작,
        연도_끝=연도_끝,
        면적대=면적대 if 면적대 else None,
        평형대=평형대 if 평형대 else None,
        세대수_범위=세대수_범위,
    )

if df_pivot.empty:
    st.warning("조건에 맞는 데이터가 없습니다. 필터를 조정해보세요.")
else:
    total_count = len(df_pivot)
    세대수_매칭 = df_pivot["세대수"].notna().sum()

    # 지도와 범례를 나란히 배치
    col_map, col_legend = st.columns([6, 1])

    with col_map:
        m = create_ranking_map(
            df_pivot,
            랭킹기준=랭킹기준,
            랭킹개수=랭킹개수,
            map_style=지도스타일,
        )
        st_folium(m, width=None, height=750, returned_objects=[])

    with col_legend:
        st.markdown("##### 연식 구분")
        for label, color in 연식_색상.items():
            if label == "정보 없음":
                continue
            st.markdown(
                f'<span style="color:{color};font-size:20px;">●</span> {label}',
                unsafe_allow_html=True,
            )
        st.caption(f"전체 {total_count:,}건 중 세대수 매칭 {세대수_매칭:,}건")

    # 랭킹 테이블
    st.subheader("랭킹 테이블")

    table_df = aggregate_by_complex(df_pivot)

    if 랭킹기준 == "회전율":
        display_df = table_df.dropna(subset=["회전율"]).sort_values("회전율", ascending=False)
    else:
        display_df = table_df.sort_values("거래량", ascending=False)

    display_df = display_df.head(랭킹개수).reset_index(drop=True)
    display_df.insert(0, "순위", list(range(1, len(display_df) + 1)))  # type: ignore[arg-type]

    display_cols = [
        "순위", "단지명", "시군구", "읍면동", "건축년도",
        "연식_구분", "거래량",
    ]
    if "세대수" in display_df.columns and bool(display_df["세대수"].notna().any()):
        display_cols.extend(["세대수", "회전율"])

    st.dataframe(
        display_df[display_cols],
        use_container_width=True,
        hide_index=True,
    )
