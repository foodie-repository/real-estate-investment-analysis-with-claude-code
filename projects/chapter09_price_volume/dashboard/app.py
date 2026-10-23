"""
Part09 가격·거래량 대시보드

실행: uv run streamlit run projects/chapter09_price_volume/dashboard/app.py
"""
import sys
import math
from collections import Counter
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (어디서든 실행 가능하도록)
_ROOT = str(Path(__file__).resolve().parents[3])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
import duckdb
from src.utils.dashboard_link import decode_selection, target_label
from projects.chapter09_price_volume.dashboard import db
from projects.chapter09_price_volume.dashboard.linked import load_linked_data
from projects.chapter09_price_volume.dashboard.linked_view import linked_sidebar

from projects.chapter09_price_volume.dashboard.constants import 평형대_목록
from projects.chapter09_price_volume.dashboard.controls import select_base_month
from projects.chapter09_price_volume.dashboard.axis_controls import render_axis_controls
from projects.chapter09_price_volume.dashboard.preprocessing import (
    get_region_options,
    get_date_range,
    get_area_range,
    get_individual_trades,
    get_monthly_summary,
    get_common_base_months,
    get_summary_stats,
)
from projects.chapter09_price_volume.dashboard.charts import (
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

st.html("""
<style>
[data-testid="stMainBlockContainer"] { padding-top: 1rem; }
[data-testid="stHeader"] { visibility: hidden; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] [data-baseweb="select"],
[data-testid="stSidebar"] [data-baseweb="select"] input,
[data-testid="stSidebar"] [data-baseweb="tag"],
[data-testid="stSidebar"] [data-testid="stRadio"] p,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    font-size: 0.8125rem;
}
/* 선택 목록은 사이드바 바깥의 팝업에 렌더링된다. */
/* 가상 목록의 행 위치와 스크롤을 함께 축소하고, 글자 크기는 보정한다. */
body:has([data-testid="stSidebar"] [role="combobox"][aria-expanded="true"])
    [data-testid="stSelectboxVirtualDropdown"] {
    zoom: 0.64;
    width: 100%;
}
body:has([data-testid="stSidebar"] [role="combobox"][aria-expanded="true"])
    :is([role="option"], [role="option"] div) {
    font-size: calc(0.8125rem / 0.64);
    line-height: 1.4;
}
[data-testid="stSidebar"] [data-baseweb="tag"] {
    height: auto;
}
[data-testid="stSidebar"] [data-baseweb="tag"] > span:first-child {
    white-space: normal;
    word-break: keep-all;
    overflow-wrap: anywhere;
    max-width: 100%;
}
.st-key-base_month_prev button,
.st-key-base_month_next button {
    width: 28px;
    min-width: 28px;
    height: 28px;
    min-height: 28px;
    padding: 0;
}
.st-key-base_month_prev button p,
.st-key-base_month_next button p {
    font-size: 12px;
}
</style>
""")


# =============================================================================
# 데이터 캐싱
# =============================================================================
@st.cache_data(ttl=3600)
def load_region_options():
    return get_region_options()


@st.cache_data(ttl=3600)
def load_date_range():
    return get_date_range()


@st.cache_data(ttl=600, max_entries=12)
def load_linked_cached(path, stamp, targets, area, period, trade_type, direct):
    return load_linked_data(path, targets, area, period, trade_type, direct)


@st.cache_data(ttl=3600)
def load_area_range(**filters):
    return get_area_range(**filters)


def region_multiselect(label, options, default=()):
    """상위 지역 변경 후에도 유효한 선택을 보존하고, 범위 밖 항목만 제거한다."""
    short_name_counts = Counter(item[2:] for item in options) if label == "단지" else {}
    district_name_counts = Counter(item[1:] for item in options) if label == "단지" else {}

    def format_option(item):
        if not isinstance(item, tuple):
            return item
        start = 0
        if label == "단지":
            start = 2 if short_name_counts[item[2:]] == 1 else (1 if district_name_counts[item[1:]] == 1 else 0)
        return f"{item[-1]} ({' '.join(item[start:-1])})"

    key = f"region_{label}"
    if key in st.session_state:
        st.session_state[key] = [item for item in st.session_state[key] if item in options]
    return st.multiselect(
        label, options, default=[item for item in default if item in options], key=key,
        format_func=format_option,
        placeholder="전체" if label != "시도" else "시도를 선택하세요",
    )


# =============================================================================
# 사이드바
# =============================================================================
link_token = st.query_params.get('selection')
linked_params = None
if link_token is not None:
    try:
        if len(st.query_params.get_all('selection')) != 1:
            raise ValueError('연결 정보가 중복되었습니다. 가격·갭 대시보드에서 다시 여세요.')
        payload = decode_selection(link_token)
        linked_params = linked_sidebar(payload,link_token,Path(db._DB_PATH))
    except (ValueError,OSError,duckdb.Error) as exc:
        st.error(f'연결 조건을 적용할 수 없습니다: {exc}')
        if st.button('연결 정보 지우기'):
            st.query_params.pop('selection',None)
            st.rerun()
        st.stop()
    선택_시도 = sorted({t[0] for t in linked_params['targets']})
    선택_시군구 = sorted({t[:2] for t in linked_params['targets']})
    선택_읍면동 = sorted({t[:3] for t in linked_params['targets']})
    선택_단지 = sorted({t[:4] for t in linked_params['targets']})
    선택_평형대 = sorted({t[5] for t in linked_params['targets']})
    선택_전용면적 = linked_params['area']
    거래유형 = linked_params['trade_type']
    시작년월,종료년월 = linked_params['period']
    직거래포함 = linked_params['direct']
else:
    with st.sidebar:
        st.header("필터")

        # 지역 선택 (계층적)
        try:
            region_data = load_region_options()
        except (OSError, ValueError, duckdb.Error) as exc:
            st.error(f"실거래 자료를 먼저 준비하고 PRICE_DB_PATH를 확인하세요: {exc}")
            st.stop()
        if not region_data:
            st.info("조회할 매매 자료가 없습니다. 수집 범위를 확인하세요.")
            st.stop()

        시도_목록 = sorted(region_data)
        선택_시도 = region_multiselect("시도", 시도_목록, ["서울특별시"] if "서울특별시" in 시도_목록 else 시도_목록[:1])
        시군구_목록 = sorted((sido, gu) for sido in 선택_시도 for gu in region_data[sido])
        선택_시군구 = region_multiselect("시군구", 시군구_목록, [("서울특별시", "강남구")])
        대상_시군구 = 선택_시군구 or 시군구_목록
        읍면동_목록 = sorted((sido, gu, dong) for sido, gu in 대상_시군구 for dong in region_data[sido][gu])
        선택_읍면동 = region_multiselect("읍면동", 읍면동_목록)
        대상_읍면동 = 선택_읍면동 or 읍면동_목록
        단지_후보 = sorted((sido, gu, dong, name) for sido, gu, dong in 대상_읍면동
                         for name in region_data[sido][gu][dong])
        선택_단지 = region_multiselect("단지", 단지_후보)

        st.divider()

        선택_평형대 = st.multiselect("평형대", 평형대_목록, default=["30평대"])
        면적_범위 = load_area_range(
            시도=선택_시도, 시군구=선택_시군구,
            읍면동=선택_읍면동 or None, 단지=선택_단지 or None, 평형대=선택_평형대,
        ) if 선택_시도 and 선택_평형대 else None
        선택_전용면적 = None
        if 면적_범위 is not None:
            _area_min = math.floor(면적_범위[0] * 10) / 10
            _area_max = max(math.ceil(면적_범위[1] * 10) / 10, round(_area_min + 0.1, 1))
            _band_key = tuple(sorted(선택_평형대))
            if st.session_state.get("area_bands") != _band_key:
                st.session_state.pop("area_range", None)
            elif "area_range" in st.session_state:
                _old_min, _old_max = st.session_state["area_range"]
                if ((_old_min, _old_max) == st.session_state.get("area_bounds")
                        or _old_max < _area_min or _old_min > _area_max):
                    st.session_state["area_range"] = (_area_min, _area_max)
                else:
                    st.session_state["area_range"] = (
                        max(_old_min, _area_min), min(_old_max, _area_max),
                    )
            st.session_state["area_bands"] = _band_key
            st.session_state["area_bounds"] = (_area_min, _area_max)
            선택_전용면적 = st.slider(
                "전용면적 (㎡)", min_value=_area_min, max_value=_area_max,
                value=(_area_min, _area_max), step=0.1, format="%.1f", key="area_range",
            )
            st.caption("선택한 평형대 안에서 전용면적을 좁힐 수 있습니다.")
        else:
            st.caption("전용면적 (㎡): 선택한 지역·단지·평형대에 면적 데이터가 없습니다.")
            st.session_state.pop("area_range", None)

        거래유형 = st.radio("거래유형", ["매매+전세", "매매만", "전세만"], index=0)

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
if not 선택_시도:
    st.info("사이드바에서 시도를 선택하세요.")
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
    전용면적=선택_전용면적,
)

linked_data = None
if linked_params:
    try:
        with st.spinner('연결한 단지·평형대의 이력을 조회하고 있습니다…'):
            linked_data = load_linked_cached(str(Path(db._DB_PATH).resolve()),Path(db._DB_PATH).stat().st_mtime_ns,**linked_params)
    except (ValueError,duckdb.Error) as exc:
        st.error(f'연결한 대상의 거래를 조회할 수 없습니다: {exc}')
        st.stop()
    if linked_data['missing']:
        st.warning('현재 기간·면적·거래유형에 자료가 없는 대상: '+
                   ' / '.join(target_label(t) for t in linked_data['missing']))

with tab1:
    with st.spinner("개별 거래 데이터 조회 중..."):
        individual_data = linked_data['individual'] if linked_data is not None else get_individual_trades(**params)

    total = sum(len(df) for df in individual_data.values())
    if total == 0:
        st.warning("선택한 조건에 해당하는 거래가 없습니다.")
    else:
        fig = create_scatter_chart(individual_data)
        render_axis_controls(fig, "individual")

with tab2:
    with st.spinner("월별 집계 데이터 조회 중..."):
        monthly_data = linked_data['monthly'] if linked_data is not None else get_monthly_summary(**params)

    total = sum(len(df) for df in monthly_data.values())
    if total == 0:
        st.warning("선택한 조건에 해당하는 거래가 없습니다.")
    else:
        _mode_column, _base_column = st.columns([1, 2])
        with _mode_column:
            _mode = st.radio("표시 방식", ["가격 (억 원)", "기준 시점 100"], horizontal=True)
        _base_month = None
        if _mode == "기준 시점 100":
            _months = sorted({int(month) for df in monthly_data.values() for month in df["계약년월"]})
            _common = get_common_base_months(monthly_data)
            _default_month = _common[0] if _common else _months[0]
            with _base_column:
                _base_month = select_base_month(_months, _default_month)
        if 선택_단지:
            st.caption(
                "단지·주소·평형대별로 선과 거래량을 나눕니다. 같은 대상은 매매·전세에서 같은 색이며, "
                "범례를 누르면 해당 대상의 가격과 거래량을 함께 숨기거나 표시합니다."
            )
            for _type, _df in (monthly_data.items() if linked_data is None else []):
                _labels = _df["비교대상"].unique()
                _missing = [f"{key[-1]} ({' '.join(key[:-1])})" for key in 선택_단지
                            if not any(label.startswith(key[-1] + " · ") and f"({' '.join(key[:-1])} " in label
                                       for label in _labels)]
                if _missing:
                    st.warning(f"선택한 기간·조건에 {_type} 거래가 없습니다: " + ", ".join(_missing))
        else:
            st.caption("현재는 선택 지역 전체의 거래를 합쳐 표시합니다. 왼쪽에서 단지를 선택하면 단지별로 비교합니다.")
        if _mode == "기준 시점 100":
            st.caption(
                f"{_base_month // 100}-{_base_month % 100:02d} = 100 · 기준월 이후를 표시합니다. "
                "120은 20% 상승, 90은 10% 하락입니다. 기준월에 거래가 없는 단지·평형대·거래유형은 비교에서 제외합니다."
            )
            if not _common:
                st.caption("모든 표시 대상에 가격이 있는 공통월이 없습니다. 기준월을 바꾸거나 비교 조건을 좁혀보세요.")
        fig = create_line_chart(monthly_data, base_month=_base_month)
        if fig.layout.meta["excluded"]:
            st.warning("기준월의 유효한 가격이 없어 비교에서 제외했습니다: " + ", ".join(fig.layout.meta["excluded"]))
        if fig.data:
            render_axis_controls(fig, "monthly_index" if _base_month is not None else "monthly_price")
            st.caption(
                "실선과 점은 거래가 있는 달의 중위가이며, 점선은 거래 없는 기간의 참고 연결선입니다. "
                "점선 구간에는 실제 가격 관측값이 없으며, 거래량은 0건으로 표시합니다. "
                "거래 건수가 적거나 면적·층 구성이 달라지면 중위가도 달라질 수 있습니다."
            )
        else:
            st.info("선택한 단지에 유효한 기준값이 있는 기준월을 선택해주세요.")

# =============================================================================
# 요약 정보
# =============================================================================
st.divider()
st.subheader("📋 요약 정보")

if 거래유형 != "전세만":
    with st.spinner("요약 통계 조회 중..."):
        stats = linked_data['stats'] if linked_data is not None else get_summary_stats(
            시도=선택_시도,
            시군구=선택_시군구,
            읍면동=선택_읍면동 or None,
            단지=선택_단지 or None,
            평형대=선택_평형대 if set(선택_평형대) != set(평형대_목록) else None,
            시작년월=시작년월,
            종료년월=종료년월,
            직거래포함=직거래포함,
            전용면적=선택_전용면적,
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
