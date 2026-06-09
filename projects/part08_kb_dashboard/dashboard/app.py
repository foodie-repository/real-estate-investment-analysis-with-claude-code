"""
KB부동산 시각화 대시보드 - Streamlit 웹 앱

3개 뷰로 구성:
1. 지도 대시보드: 4개 지표를 2×2 코로플레스 지도로 표시
2. 지도 상세: 선택한 지표 1개를 크게 표시
3. 시계열 분석: 선 그래프 + 히트맵 테이블

실행: uv run streamlit run projects/part08_kb_dashboard/dashboard/app.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (어디서든 실행 가능하도록)
_ROOT = str(Path(__file__).resolve().parents[3])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
from streamlit_folium import st_folium

from projects.part08_kb_dashboard.dashboard.constants import (
    SIDO_MAPPING, INDICATORS, MAP_LAYOUT,
)
from projects.part08_kb_dashboard.dashboard.geo import (
    load_geojson, filter_by_sido, get_sido_list, get_sigungu_list,
    get_sig_cd_for_names,
)
from projects.part08_kb_dashboard.dashboard.preprocessing import (
    get_all_indicators, get_timeseries, get_timeseries_sido, get_ts_date_range,
)
from projects.part08_kb_dashboard.dashboard.choropleth import (
    create_base_map, create_data_layer,
)
from projects.part08_kb_dashboard.dashboard.charts import (
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
    /* 히트맵 테이블 폰트 크기 축소 */
    .stDataFrame td, .stDataFrame th { font-size: 11px !important; }
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
start_year, start_month, end_year, end_month = get_ts_date_range()
geojson = load_geojson_cached()
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
    지표_선택 = st.sidebar.selectbox("지표", _시계열_지표)

    st.sidebar.divider()

    # 2. 시도 선택 (선택 사항)
    시도_선택 = st.sidebar.multiselect("시도", 시도_표시목록, key="ts_sido")
    시도_정식명 = [SIDO_MAPPING.get(s, s) for s in 시도_선택]

    # 3. 시군구 선택: 시도 선택 시 해당 시도만, 미선택 시 전체
    if 시도_선택:
        if len(시도_선택) == 1:
            시군구_목록 = sorted(get_sigungu_list(geojson, 시도_정식명[0]))
        else:
            _후보 = []
            for sido in 시도_정식명:
                for sg in get_sigungu_list(geojson, sido):
                    _후보.append((sg, sido))
            _이름_빈도 = {}
            for sg, _ in _후보:
                _이름_빈도[sg] = _이름_빈도.get(sg, 0) + 1
            시군구_목록 = sorted(set(
                f"{sg} ({sido})" if _이름_빈도[sg] > 1 else sg
                for sg, sido in _후보
            ))
    else:
        _전체_후보 = [
            (f["properties"]["sig_kor_nm"], f["properties"]["sig_cd"][:2])
            for f in geojson["features"]
        ]
        _이름_빈도 = {}
        for sg, _ in _전체_후보:
            _이름_빈도[sg] = _이름_빈도.get(sg, 0) + 1
        _시도코드_정식명 = {v[:2]: v for v in SIDO_MAPPING.values()}
        시군구_목록 = sorted(set(
            f"{sg} ({_시도코드_정식명.get(cd, cd)})" if _이름_빈도[sg] > 1 else sg
            for sg, cd in _전체_후보
        ))

    시군구_선택 = st.sidebar.multiselect("시군구", 시군구_목록, key="ts_sigungu")

# ─────────────────────────────────────────────────
# 지도 뷰: 시도 → 날짜 → (지표)
# ─────────────────────────────────────────────────
else:
    # 시도 선택
    시도_선택 = st.sidebar.multiselect(
        "시도", 시도_표시목록, default=["서울", "경기"], key="map_sido",
    )
    시도_정식명 = [SIDO_MAPPING.get(s, s) for s in 시도_선택]

    st.sidebar.divider()

    # 날짜 선택
    _연월_목록 = []
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            if y == start_year and m < start_month:
                continue
            if y == end_year and m > end_month:
                break
            _연월_목록.append((y, m))

    # session_state 초기화 (최신 월)
    if "선택_연월_idx" not in st.session_state:
        st.session_state["선택_연월_idx"] = len(_연월_목록) - 1

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
    _현재_연, _현재_월 = _연월_목록[st.session_state["선택_연월_idx"]]
    with _col_display:
        st.markdown(
            f"<div style='text-align:center;font-size:15px;font-weight:600;"
            f"padding-top:6px'>{_현재_연}.{_현재_월:02d}</div>",
            unsafe_allow_html=True,
        )

    # 슬라이더로 대략적 위치 이동
    _슬라이더_연월 = st.sidebar.select_slider(
        "기간",
        options=list(range(len(_연월_목록))),
        value=st.session_state["선택_연월_idx"],
        format_func=lambda i: f"{_연월_목록[i][0]}.{_연월_목록[i][1]:02d}",
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
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)
    cols = [row1_col1, row1_col2, row2_col1, row2_col2]

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
            sig_cd_col = "sig_kor_nm"

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
            unit=info["unit"],
            decimals=0 if info["type"] == "count" else 1,
        )

        with cols[i]:
            st.subheader(indicator_name)
            st_folium(
                base, width=None, height=400,
                feature_group_to_add=fg,
                returned_objects=[],
                key=f"dashboard_{i}",
            )


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
        sig_cd_col = "sig_kor_nm"

    # base map: 시도 선택이 같으면 동일 HTML → 줌 보존
    base = create_base_map(filtered_geojson)

    fg = create_data_layer(
        geojson=filtered_geojson,
        df=df,
        value_col=value_col,
        sig_cd_col=sig_cd_col,
        title=f"{지표_선택} ({선택_연도}.{선택_월:02d})",
        unit=info["unit"],
        decimals=0 if info["type"] == "count" else 1,
    )

    st.subheader(f"{지표_선택} ({선택_연도}.{선택_월:02d})")
    st_folium(
        base, width=None, height=850,
        feature_group_to_add=fg,
        returned_objects=[],
        key="detail",
    )


# ─────────────────────────────────────────────────
# 뷰 3: 시계열 분석
# ─────────────────────────────────────────────────
else:
    info = INDICATORS[지표_선택]

    # 전체 기간 조회
    _ts_start, _, _ts_end, _ = get_ts_date_range()

    with st.spinner("시계열 데이터 조회 중..."):
        if 시군구_선택:
            # 병기 형태("강서구 (서울특별시)")를 파싱하여 시군구명·시도별로 그룹화
            _파싱_결과 = []
            for _항목 in 시군구_선택:
                if _항목.endswith(")") and " (" in _항목:
                    _sg, _sido = _항목.rsplit(" (", 1)
                    _파싱_결과.append((_sg, _sido.rstrip(")")))
                else:
                    _파싱_결과.append((_항목, None))

            _sig_cds = []
            for _sg, _sido in _파싱_결과:
                if _sido:
                    _g = filter_by_sido(geojson, [_sido])
                else:
                    _g = filter_by_sido(geojson, 시도_정식명) if 시도_선택 else geojson
                _sig_cds.extend(get_sig_cd_for_names(_g, [_sg]))
            sig_cds = list(dict.fromkeys(_sig_cds))
            if not sig_cds:
                st.warning("선택한 시군구의 코드를 찾을 수 없습니다.")
                st.stop()
            df_ts = get_timeseries(
                table=info.get("ts_table", info["table"]),
                value_col=info["value_col"],
                indicator_type=info["type"],
                sig_cds=sig_cds,
                start_year=_ts_start,
                end_year=_ts_end,
            )
        else:
            # 시도별 비교
            df_ts = get_timeseries_sido(
                table=info.get("ts_table", info["table"]),
                value_col=info["value_col"],
                indicator_type=info["type"],
                sido_names=시도_선택,
                start_year=_ts_start,
                end_year=_ts_end,
            )

    if df_ts.empty:
        st.warning("해당 기간에 데이터가 없습니다.")
        st.stop()

    # 기간 선택 슬라이더 (선 그래프 + 히트맵 동기화)
    _날짜_목록 = sorted(df_ts["날짜"].unique())
    _날짜_라벨 = [d.strftime("%Y-%m") if hasattr(d, "strftime")
                 else str(d)[:7] for d in _날짜_목록]

    # 기본값: 최근 5년 또는 전체 (데이터가 5년 미만이면 전체)
    _5년전_idx = max(0, len(_날짜_목록) - 60)  # 60개월 ≈ 5년

    _범위 = st.select_slider(
        "기간 선택",
        options=list(range(len(_날짜_목록))),
        value=(_5년전_idx, len(_날짜_목록) - 1),
        format_func=lambda i: _날짜_라벨[i],
    )

    # 선택 기간으로 데이터 필터링
    _시작_날짜 = _날짜_목록[_범위[0]]
    _종료_날짜 = _날짜_목록[_범위[1]]
    df_filtered = df_ts[  # type: ignore[index]
        (df_ts["날짜"] >= _시작_날짜) & (df_ts["날짜"] <= _종료_날짜)
    ].copy()

    _시작_라벨 = _날짜_라벨[_범위[0]]
    _종료_라벨 = _날짜_라벨[_범위[1]]

    # 선 그래프
    st.subheader(f"{지표_선택} 추이")
    fig = create_line_chart(
        df=df_filtered,  # type: ignore[arg-type]
        title=f"{지표_선택} ({_시작_라벨} ~ {_종료_라벨})",
        unit=info["unit"],
    )
    st.plotly_chart(fig, use_container_width=True)

    # 히트맵 테이블
    st.subheader(f"{지표_선택} 히트맵")
    styled = create_heatmap_table(
        df=df_filtered,  # type: ignore[arg-type]
        unit=info["unit"],
    )
    st.dataframe(styled, use_container_width=True, height=500)
