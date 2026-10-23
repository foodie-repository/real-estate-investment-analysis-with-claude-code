"""
KB부동산 시각화 대시보드 - Streamlit 웹 앱

3개 뷰로 구성:
1. 지도 대시보드: 4개 지표를 2×2 코로플레스 지도로 표시
2. 지도 상세: 선택한 지표 1개를 크게 표시
3. 시계열 분석: 선 그래프 + 히트맵 테이블

실행: uv run streamlit run projects/chapter06_kb_dashboard/dashboard/app.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (어디서든 실행 가능하도록)
_ROOT = str(Path(__file__).resolve().parents[3])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import duckdb
import streamlit as st
from streamlit_folium import st_folium

from projects.chapter06_kb_dashboard.dashboard.constants import (
    SIDO_MAPPING, INDICATORS, MAP_LAYOUT,
)
from projects.chapter06_kb_dashboard.dashboard.geo import (
    build_sigungu_display_code_map, load_geojson, filter_by_sido, get_sido_list,
)
from projects.chapter06_kb_dashboard.dashboard.preprocessing import (
    get_all_indicators, get_map_dates, get_timeseries, get_timeseries_sido,
    get_ts_date_range, get_date_range, rebase_timeseries,
)
from projects.chapter06_kb_dashboard.dashboard.choropleth import (
    create_base_map, create_data_layer, get_parent_fallback_names,
    color_legend_html, _get_feature_value,
)
from projects.chapter06_kb_dashboard.dashboard.axis_controls import render_axis_controls
from projects.chapter06_kb_dashboard.dashboard.charts import (
    create_line_chart, create_heatmap_table,
)


# =============================================================================
# 페이지 설정
# =============================================================================
st.set_page_config(
    page_title="KB부동산 시각화 대시보드",
    page_icon="🏠",
    layout="wide",
)

st.markdown(
    """<style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    header { visibility: hidden; }
    .st-key-kb_map_grid { gap: 8px; }
    .st-key-kb_map_grid h3 { font-size: 20px; line-height: 1.25; padding: 0 0 4px; }
    .st-key-kb_map_grid [data-testid="stVerticalBlock"] { gap: 8px; }
    .st-key-kb_map_grid iframe { height: clamp(210px, calc((100dvh - 250px) / 2), 480px) !important; }
    [class*="st-key-kb_map_panel_"] > [data-testid="stHorizontalBlock"] { gap: 8px; flex-wrap: nowrap; }
    [class*="st-key-kb_map_panel_"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
        flex: 0 0 64px; min-width: 64px;
    }
    .kb-color-legend { display: flex; gap: 4px; height: clamp(210px, calc((100dvh - 250px) / 2), 480px); padding: 12px 0 20px; box-sizing: border-box; }
    .kb-color-ramp { width: 10px; flex-shrink: 0; }
    .kb-color-ticks { display: flex; flex-direction: column; justify-content: space-between; font-size: 11px; color: #555; }
    .st-key-kb_detail_legend .kb-color-legend { height: 850px; }
    /* 히트맵 테이블 폰트 크기 축소 */
    .stDataFrame td, .stDataFrame th { font-size: 11px !important; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-baseweb="select"],
    [data-testid="stSidebar"] [data-baseweb="select"] div,
    [data-testid="stSidebar"] [data-baseweb="select"] input,
    [data-testid="stSidebar"] [data-baseweb="tag"] {
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
    .st-key-kb_base_period [data-baseweb="slider"] { filter: grayscale(1); }
    .st-key-kb_base_period [data-baseweb="slider"] div:has(> [role="slider"]) + div { opacity: 0.5; }
    .st-key-kb_base_period [role="slider"] { background-color: #b8b8b8; }
    </style>""",
    unsafe_allow_html=True,
)

st.title("KB부동산 시각화 대시보드")


# =============================================================================
# 캐싱
# =============================================================================
@st.cache_resource
def load_geojson_cached():
    """시군구 경계 GeoJSON을 캐싱하여 로드한다."""
    return load_geojson()


# =============================================================================
# 공통 데이터 로드
# =============================================================================
try:
    map_dates = get_map_dates()
    geojson = load_geojson_cached()
except (OSError, ValueError, duckdb.Error) as exc:
    st.error(f"KB 통계·실거래 자료와 시군구 경계지도를 먼저 준비하세요. KB_DB_PATH와 data/boundaries/시군구.geojson을 확인하세요: {exc}")
    st.stop()
if not map_dates:
    st.info("조회할 KB 통계의 기간이 없습니다. 수집 결과를 확인하세요.")
    st.stop()
시도_목록 = get_sido_list(geojson)
시도_단축명 = {v: k for k, v in SIDO_MAPPING.items()}
시도_표시목록 = [시도_단축명.get(s, s) for s in 시도_목록]


# =============================================================================
# 사이드바 필터
# =============================================================================
st.sidebar.header("필터 설정")

선택_연도: int = 0
선택_월: int = 0
filtered_geojson: dict = {}
시군구_선택: list[str] = []
지표_선택: str = ""
_index_mode = False

# 뷰 선택
뷰 = st.sidebar.radio(
    "뷰 선택",
    ["지도 대시보드", "지도 상세", "시계열 분석"],
    horizontal=True,
)

st.sidebar.divider()

# ─────────────────────────────────────────────────
# 시계열 분석 뷰: 지표 → 시도 → 시군구
# ─────────────────────────────────────────────────
if 뷰 == "시계열 분석":
    # 1. 지표 선택 (거래량 제외 — KB 지수 기반만 지원)
    _시계열_지표 = [k for k, v in INDICATORS.items() if v["type"] != "count"]
    지표_선택 = st.sidebar.selectbox(
        "지표", _시계열_지표,
        format_func=lambda name: name.replace(" 전년동월대비 증감률", "가격"),
    )
    if INDICATORS[지표_선택]["type"] == "yoy":
        _index_mode = st.sidebar.radio(
            "비교 방식", ["전년동월대비 증감률", "시작 시점 100"],
        ) == "시작 시점 100"

    st.sidebar.divider()

    # 2. 시도 선택 (선택 사항)
    시도_선택 = st.sidebar.multiselect(
        "시도", 시도_표시목록, default=[s for s in ["서울", "경기"] if s in 시도_표시목록] or 시도_표시목록[:1], key="ts_sido",
    )
    시도_정식명 = [SIDO_MAPPING.get(s, s) for s in 시도_선택]

    # 3. 시군구 선택: 표시 문자열을 다시 해석하지 않고 실제 sig_cd와 직접 연결
    _시군구_geojson = (
        filter_by_sido(geojson, 시도_정식명) if 시도_선택 else geojson
    )
    _시군구_표시_코드 = build_sigungu_display_code_map(_시군구_geojson)
    시군구_목록 = sorted(_시군구_표시_코드)

    시군구_선택 = st.sidebar.multiselect("시군구", 시군구_목록, key="ts_sigungu")

# ─────────────────────────────────────────────────
# 지도 뷰: 시도 → 날짜 → (지표)
# ─────────────────────────────────────────────────
else:
    # 시도 선택
    시도_선택 = st.sidebar.multiselect(
        "시도", 시도_표시목록, default=["서울"] if "서울" in 시도_표시목록 else 시도_표시목록[:1], key="map_sido",
    )
    시도_정식명 = [SIDO_MAPPING.get(s, s) for s in 시도_선택]

    st.sidebar.divider()

    # 날짜 선택
    _연월_목록 = map_dates

    # session_state 초기화 (최신 월)
    if "선택_연월_idx" not in st.session_state:
        st.session_state["선택_연월_idx"] = len(_연월_목록) - 1
    else:
        st.session_state["선택_연월_idx"] = min(
            st.session_state["선택_연월_idx"], len(_연월_목록) - 1,
        )

    # ◀ 이전월 / 다음월 ▶ 버튼
    _col_prev, _col_display, _col_next = st.sidebar.columns([1, 2, 1])
    with _col_prev:
        if st.button("◀", use_container_width=True):
            if st.session_state["선택_연월_idx"] > 0:
                st.session_state["선택_연월_idx"] -= 1
    with _col_next:
        if st.button("▶", use_container_width=True):
            if st.session_state["선택_연월_idx"] < len(_연월_목록) - 1:
                st.session_state["선택_연월_idx"] += 1

    # 현재 선택된 연월 표시
    _현재_연월 = _연월_목록[st.session_state["선택_연월_idx"]]
    _현재_연, _현재_월 = _현재_연월 // 100, _현재_연월 % 100
    with _col_display:
        st.markdown(
            f"<div style='text-align:center;font-size:13px;font-weight:600;"
            f"padding-top:6px'>{_현재_연}.{_현재_월:02d}</div>",
            unsafe_allow_html=True,
        )

    # 슬라이더로 대략적 위치 이동
    _슬라이더_연월 = st.sidebar.select_slider(
        "기간",
        options=list(range(len(_연월_목록))),
        value=st.session_state["선택_연월_idx"],
        format_func=lambda i: f"{_연월_목록[i] // 100}.{_연월_목록[i] % 100:02d}",
        label_visibility="collapsed",
    )
    if _슬라이더_연월 != st.session_state["선택_연월_idx"]:
        st.session_state["선택_연월_idx"] = _슬라이더_연월
        st.rerun()

    선택_연도, 선택_월 = _현재_연, _현재_월

    # 지도 상세에서만 지표 선택
    if 뷰 == "지도 상세":
        st.sidebar.divider()
        지표_선택 = st.sidebar.selectbox("지표", list(INDICATORS.keys()))


# =============================================================================
# 메인 콘텐츠
# =============================================================================

# 지도 뷰 검증
if 뷰 != "시계열 분석":
    if not 시도_선택:
        st.warning("시도를 1개 이상 선택해주세요.")
        st.stop()

    filtered_geojson = filter_by_sido(geojson, 시도_정식명)
    st.caption(f"**{', '.join(시도_선택)}** | {선택_연도}년 {선택_월}월")

# 시계열 뷰 검증
else:
    if not 시도_선택 and not 시군구_선택:
        st.warning("시도 또는 시군구를 1개 이상 선택해주세요.")
        st.stop()

    _caption_labels = 시군구_선택 if 시군구_선택 else 시도_선택
    st.caption(f"**{', '.join(_caption_labels)}**")


# ─────────────────────────────────────────────────
# 뷰 1: 지도 대시보드 (2×2 코로플레스)
# ─────────────────────────────────────────────────
if 뷰 == "지도 대시보드":
    with st.spinner("데이터 조회 중..."):
        indicators = get_all_indicators(선택_연도, 선택_월)

    # 2×2 배치
    grid = st.container(key="kb_map_grid")
    row1_col1, row1_col2 = grid.columns(2)
    row2_col1, row2_col2 = grid.columns(2)
    cols = [row1_col1, row1_col2, row2_col1, row2_col2]
    map_notes = []

    for i, indicator_name in enumerate(MAP_LAYOUT):
        info = INDICATORS[indicator_name]
        df = indicators.get(indicator_name)

        if df is None or df.empty:
            with cols[i]:
                st.warning(f"{indicator_name}: 데이터 없음")
            continue

        # 값 컬럼명 결정
        if info["type"] == "yoy":
            value_col = "증감률"
            sig_cd_col = "sig_cd"
        elif info["type"] == "direct":
            value_col = "전세가율"
            sig_cd_col = "sig_cd"
        else:  # count
            value_col = "거래량"
            sig_cd_col = "full_nm"

        # base map: 시도 선택이 같으면 동일 HTML → 컴포넌트 키 불변 → 줌 보존
        # 각 슬롯마다 별도 base map 생성 (st_folium이 내부적으로 map 객체를 변경하므로)
        base = create_base_map(filtered_geojson)

        # 데이터 레이어를 FeatureGroup으로 분리 → base map HTML 불변
        fg = create_data_layer(
            geojson=filtered_geojson,
            df=df,
            value_col=value_col,
            sig_cd_col=sig_cd_col,
            title=f"{indicator_name} ({선택_연도}.{선택_월:02d})",
            center_mode=info["type"],
            unit=info["unit"],
            decimals=0 if info["type"] == "count" else 1,
        )
        value_map = dict(zip(df[sig_cd_col].astype(str), df[value_col]))
        parent_fallback_names = get_parent_fallback_names(value_map, filtered_geojson)
        missing = [f["properties"]["full_nm"] for f in filtered_geojson["features"]
                   if _get_feature_value(value_map, f["properties"]) is None]
        if missing:
            map_notes.append(f"{indicator_name} · 자료 없음 {len(missing)}개: " + ", ".join(missing))
        if parent_fallback_names:
            map_notes.append("상위 도시 값 사용: " + ", ".join(parent_fallback_names))

        with cols[i]:
            st.subheader(indicator_name)
            with st.container(key=f"kb_map_panel_{i}"):
                map_col, legend_col = st.columns([10, 1], gap="small")
                with map_col:
                    st_folium(
                        base, width=None, height=320,
                        feature_group_to_add=fg,
                        returned_objects=[],
                        key=f"dashboard_{i}",
                    )
                with legend_col:
                    st.html(color_legend_html(df, value_col, info["type"], info["unit"]))
    with st.expander("지도 읽기 · 자료가 없는 지역 확인"):
        st.caption("라벨은 색상 중심에서 차이가 큰 지역부터 겹치지 않게 표시합니다. 숨겨진 지역은 확대하거나 마우스를 올려 값을 확인하세요. 회색은 자료 없음이며 0건이 아닙니다.")
        for note in dict.fromkeys(map_notes):
            st.write(note)
        if not map_notes:
            st.write("선택 지역의 네 지표가 모두 경계에 연결되었습니다.")


# ─────────────────────────────────────────────────
# 뷰 2: 지도 상세 (단일 지표 확대)
# ─────────────────────────────────────────────────
elif 뷰 == "지도 상세":
    info = INDICATORS[지표_선택]

    with st.spinner("데이터 조회 중..."):
        indicators = get_all_indicators(선택_연도, 선택_월)

    df = indicators.get(지표_선택)

    if df is None or df.empty:
        st.warning(f"{지표_선택}: 데이터 없음")
        st.stop()

    # 값 컬럼명 결정
    if info["type"] == "yoy":
        value_col = "증감률"
        sig_cd_col = "sig_cd"
    elif info["type"] == "direct":
        value_col = "전세가율"
        sig_cd_col = "sig_cd"
    else:  # count
        value_col = "거래량"
        sig_cd_col = "full_nm"

    # base map: 시도 선택이 같으면 동일 HTML → 줌 보존
    base = create_base_map(filtered_geojson)

    fg = create_data_layer(
        geojson=filtered_geojson,
        df=df,
        value_col=value_col,
        sig_cd_col=sig_cd_col,
        title=f"{지표_선택} ({선택_연도}.{선택_월:02d})",
        center_mode=info["type"],
        unit=info["unit"],
        decimals=0 if info["type"] == "count" else 1,
    )
    value_map = dict(zip(df[sig_cd_col].astype(str), df[value_col]))
    parent_fallback_names = get_parent_fallback_names(value_map, filtered_geojson)

    st.subheader(f"{지표_선택} ({선택_연도}.{선택_월:02d})")
    map_col, legend_col = st.columns([20, 1], gap="small")
    with map_col:
        st_folium(
            base, width=None, height=850,
            feature_group_to_add=fg,
            returned_objects=[],
            key="detail",
        )
    with legend_col, st.container(key="kb_detail_legend"):
        st.html(color_legend_html(df, value_col, info["type"], info["unit"]))
    if parent_fallback_names:
        st.caption(
            "※ " + ", ".join(parent_fallback_names)
            + ": 신설 일반구 값이 없어 기존 상위 도시 값을 표시합니다."
        )


# ─────────────────────────────────────────────────
# 뷰 3: 시계열 분석
# ─────────────────────────────────────────────────
else:
    info = INDICATORS[지표_선택]

    # 전체 기간 조회
    if _index_mode or info["type"] == "direct":
        _ts_start, _, _ts_end, _ = get_date_range(info["table"], include_history=_index_mode)
    else:
        _ts_start, _, _ts_end, _ = get_ts_date_range(
            info["table"], "시군구" if 시군구_선택 else "시도",
        )
    _table = info["table"] if _index_mode else info.get("ts_table", info["table"])
    _indicator_type = "index" if _index_mode else info["type"]

    with st.spinner("시계열 데이터 조회 중..."):
        if 시군구_선택:
            sig_cds = list(dict.fromkeys(
                _시군구_표시_코드[display]
                for display in 시군구_선택
                if display in _시군구_표시_코드
            ))
            if not sig_cds:
                st.warning("선택한 시군구의 코드를 찾을 수 없습니다.")
                st.stop()
            df_ts = get_timeseries(
                table=_table,
                value_col=info["value_col"],
                indicator_type=_indicator_type,
                sig_cds=sig_cds,
                start_year=_ts_start,
                end_year=_ts_end,
            )
        else:
            # 시도별 비교
            df_ts = get_timeseries_sido(
                table=_table,
                value_col=info["value_col"],
                indicator_type=_indicator_type,
                sido_names=시도_선택,
                start_year=_ts_start,
                end_year=_ts_end,
            )

    if df_ts.empty:
        st.warning("해당 기간에 데이터가 없습니다.")
        st.stop()

    if 시군구_선택:
        _display_names = {code: display for display, code in _시군구_표시_코드.items()}
        df_ts["지역명"] = df_ts["sig_cd"].map(_display_names).fillna(df_ts["지역명"])

    # 기간 선택 슬라이더 (선 그래프 + 히트맵 동기화)
    _날짜_목록 = sorted(df_ts["날짜"].unique())
    _날짜_라벨 = [d.strftime("%Y-%m") if hasattr(d, "strftime")
                 else str(d)[:7] for d in _날짜_목록]

    # 전체 기간을 기본으로 표시하고, 지수 비교에서는 기준월을 직접 고른다.
    if _index_mode:
        _valid = df_ts.loc[(df_ts["값"] > 0) & (df_ts["값"] < float("inf"))]
        _counts = _valid.groupby("날짜")["지역명"].nunique()
        _common_dates = _counts[_counts == len(시군구_선택 or 시도_선택)].index
        _default_start = _날짜_목록.index(_common_dates.min()) if len(_common_dates) else 0
        with st.container(key="kb_base_period"):
            if len(_날짜_목록) > 1:
                _범위 = st.select_slider(
                    "비교 기간 · 시작월(기준값 100) ~ 종료월",
                    options=range(len(_날짜_목록)),
                    value=(_default_start, len(_날짜_목록) - 1),
                    format_func=lambda i: _날짜_라벨[i],
                )
            else:
                _범위 = (0, 0)
                st.caption(f"비교 기간: {_날짜_라벨[0]} (기준값 100)")
        st.caption("기본 기간은 선택한 지역 모두에 기준값이 있는 첫 달부터 마지막 달까지입니다.")
    else:
        _범위 = (0, len(_날짜_목록) - 1)

    # 선택 기간으로 데이터 필터링
    _시작_날짜 = _날짜_목록[_범위[0]]
    _종료_날짜 = _날짜_목록[_범위[1]]
    df_filtered = df_ts[  # type: ignore[index]
        (df_ts["날짜"] >= _시작_날짜) & (df_ts["날짜"] <= _종료_날짜)
    ].copy()

    _시작_라벨 = _날짜_라벨[_범위[0]]
    _종료_라벨 = _날짜_라벨[_범위[1]]

    _title = 지표_선택
    _unit = info["unit"]
    if _index_mode:
        df_filtered, _excluded = rebase_timeseries(
            df_filtered, _시작_날짜, expected_regions=시군구_선택 or 시도_선택,
        )
        if _excluded:
            st.warning("시작월의 유효한 가격지수가 없어 비교에서 제외했습니다: " + ", ".join(_excluded))
        if df_filtered.empty:
            st.info("선택한 지역에 유효한 기준값이 있는 시작월을 선택해주세요.")
            st.stop()
        _title = 지표_선택.replace(" 전년동월대비 증감률", "가격 · 시작 시점 대비")
        _unit = "지수"
        st.caption(
            f"기준월 {_시작_라벨} = 100 · 120은 기준월보다 20% 상승, 90은 10% 하락입니다. "
            "시작월을 바꾸면 비교 기준도 바뀝니다."
        )
        if df_filtered["복원값"].any():
            _history_end = df_filtered.loc[df_filtered["복원값"], "날짜"].max().strftime("%Y-%m")
            st.caption(
                f"※ {_history_end}까지의 과거 구간에는 KB 전월 대비 증감률로 복원한 지수가 포함됩니다. "
                "저장된 원본 지수에 연결해 계산하며, 증감률이 누락된 구간은 연결하지 않습니다. "
                "증감률의 반올림에 따라 원래 공표 지수와 차이가 날 수 있습니다."
            )

    # 선 그래프
    st.subheader(f"{_title} 추이")
    fig = create_line_chart(
        df=df_filtered,  # type: ignore[arg-type]
        title=f"{_title} ({_시작_라벨} ~ {_종료_라벨})",
        unit=_unit,
        baseline=100 if _index_mode else None,
    )
    _view_start, _view_end = render_axis_controls(
        fig, df_filtered, _unit, key=f"kb_ts_{지표_선택}_{_index_mode}",
        baseline=100 if _index_mode else None,
    )
    if _index_mode:
        st.caption("X축 슬라이더는 표시 기간만 조절합니다. 기준값 100의 시작월은 위에서 변경합니다.")
    df_visible = df_filtered[
        (df_filtered["날짜"] >= _view_start) & (df_filtered["날짜"] <= _view_end)
    ]

    # 히트맵 테이블
    st.subheader(f"{_title} 히트맵")
    styled = create_heatmap_table(
        df=df_visible,
        center_mode=_indicator_type,
        unit=_unit,
    )
    st.dataframe(styled, use_container_width=True, height="content")
