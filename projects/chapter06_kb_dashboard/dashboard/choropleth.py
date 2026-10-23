"""
Folium 코로플레스 지도 빌더

시군구 경계 GeoJSON 위에 지표 값을 색상으로 채워 코로플레스 맵을 생성한다.
"""
import math
import html

import folium
import branca.colormap as cm
import pandas as pd
from branca.element import MacroElement, Template

from projects.chapter06_kb_dashboard.dashboard.constants import DIVERGING_COLORS
from src.config import get_vworld_tiles


PARENT_SIG_CD_FALLBACKS = {
    "41591": "41590",
    "41593": "41590",
    "41595": "41590",
    "41597": "41590",
}


class _ReadableLabels(MacroElement):
    """현재 지도 픽셀 좌표에서 겹치는 라벨을 숨기고 확대할 때 다시 배치한다."""
    _template = Template("""{% macro script(this, kwargs) %}
    (function () {
        const map = {{ this._parent.get_name() }};
        const container = map.getContainer();
        container.style.height = '100vh';
        let pending = false;
        function arrange() {
            pending = false;
            const area = container.getBoundingClientRect(), accepted = [];
            const labels = Array.from(container.querySelectorAll('.kb-region-label'));
            labels.sort((a, b) => Number(b.dataset.priority) - Number(a.dataset.priority)
                || a.textContent.localeCompare(b.textContent));
            labels.forEach(label => {
                label.style.visibility = 'hidden';
                const r = label.getBoundingClientRect(), pad = 2;
                const fits = r.left >= area.left + 4 && r.right <= area.right - 4
                    && r.top >= area.top + 4 && r.bottom <= area.bottom - 24;
                const overlaps = accepted.some(b => r.left < b.right + pad && r.right > b.left - pad
                    && r.top < b.bottom + pad && r.bottom > b.top - pad);
                if (fits && !overlaps) { label.style.visibility = 'visible'; accepted.push(r); }
            });
        }
        function schedule() { if (!pending) { pending = true; requestAnimationFrame(arrange); } }
        map.on('moveend zoomend layeradd', schedule);
        new MutationObserver(schedule).observe(container.querySelector('.leaflet-marker-pane'), {childList:true, subtree:true});
        new ResizeObserver(() => { map.invalidateSize({pan:false}); schedule(); }).observe(container);
        map.whenReady(schedule);
    })();
    {% endmacro %}""")


def color_legend_html(df, value_col, center_mode, unit="%") -> str:
    """지도 영역 밖에 표시할 제목 없는 세로 색상 범례."""
    bounds = get_color_scale_bounds(df[value_col], center_mode)
    if bounds is None:
        return ""
    low, high, center = bounds
    decimals = 0 if unit == "건" else 1
    gradient = ",".join(reversed(DIVERGING_COLORS))
    ticks = "".join(f'<span>{v:,.{decimals}f}</span>' for v in (high, center, low))
    return (f'<div class="kb-color-legend" aria-label="색상 범위 ({unit})">'
            f'<div class="kb-color-ramp" style="background:linear-gradient(to bottom,{gradient})"></div>'
            f'<div class="kb-color-ticks">{ticks}</div></div>')


def _is_finite_value(value) -> bool:
    """결측치와 무한대를 제외한 수치인지 확인한다."""
    if not pd.notna(value):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _get_feature_value(value_map: dict, properties: dict):
    """지역코드, 시도를 포함한 전체 지역명, 시군구명 순으로 값을 찾는다."""
    sig_cd = properties.get("sig_cd")
    for key in (
        sig_cd,
        properties.get("full_nm"),
        properties.get("sig_kor_nm"),
    ):
        if key in value_map and _is_finite_value(value_map[key]):
            return value_map[key]

    # KB가 화성시 신설 일반구 지수를 아직 제공하지 않으면 기존 화성시 값을 쓴다.
    parent_city_code = PARENT_SIG_CD_FALLBACKS.get(sig_cd)
    if parent_city_code in value_map and _is_finite_value(value_map[parent_city_code]):
        return value_map[parent_city_code]
    return None


def get_parent_fallback_names(value_map: dict, geojson: dict) -> list[str]:
    """신설 일반구 경계에 상위 도시 값을 쓰는 지역명을 반환한다."""
    names = []
    for feature in geojson.get("features", []):
        properties = feature["properties"]
        direct_keys = (
            properties.get("sig_cd"),
            properties.get("full_nm"),
            properties.get("sig_kor_nm"),
        )
        if any(
            key in value_map and _is_finite_value(value_map[key])
            for key in direct_keys
        ):
            continue

        sig_cd = properties.get("sig_cd")
        parent_city_code = PARENT_SIG_CD_FALLBACKS.get(sig_cd)
        if (
            parent_city_code in value_map
            and _is_finite_value(value_map[parent_city_code])
        ):
            names.append(
                properties.get("full_nm", properties.get("sig_kor_nm", sig_cd))
            )
    return names


def get_color_scale_bounds(
    values: pd.Series,
    center_mode: str,
) -> tuple[float, float, float] | None:
    """유효한 수치만으로 지표 유형에 맞는 색상 범위(최저, 최고, 중심)를 계산한다.

    증감률과 전세가율은 중심 양쪽에 대칭 범위를 쓴다. 거래량은 0 아래로
    내려가지 않으므로 실제 최솟값과 최댓값을 양 끝으로 삼는다.
    """
    valid = pd.to_numeric(values, errors="coerce")
    valid = valid[valid.map(_is_finite_value)]
    if valid.empty:
        return None

    data_min = float(valid.min())
    data_max = float(valid.max())
    if center_mode == "count":
        center = float(valid.median())
        # 양쪽 구간 폭이 0이면 색상 보간 구간을 만들 수 없으므로 1건만 벌린다.
        low = data_min if data_min < center else center - 1.0
        high = data_max if data_max > center else center + 1.0
        return low, high, center
    if center_mode == "yoy":
        center = 0.0
    elif center_mode == "direct":
        center = float(valid.median())
    else:
        raise ValueError(f"지원하지 않는 색상 중심 모드입니다: {center_mode}")

    abs_max = max(abs(data_min - center), abs(data_max - center))
    if abs_max == 0:
        abs_max = 1.0
    return center - abs_max, center + abs_max, center


def _get_colormap(
    vmin: float, vmax: float, center: float = 0.0,
) -> cm.LinearColormap:
    """
    Diverging colormap을 생성한다 (파랑↔흰색↔빨강).

    vmin은 가장 진한 파랑, center는 흰색, vmax는 가장 진한 빨강이다.
    center 아래와 위 구간에 색상을 각각 고르게 배치하므로,
    대칭 범위를 넘기면 기존과 같은 선형 색상이 된다.

    Args:
        vmin: 색상 범위 최저값
        vmax: 색상 범위 최고값
        center: 색상 중심값 (증감률은 0, 전세가율·거래량은 중앙값)
    """
    half = len(DIVERGING_COLORS) // 2
    lower = [vmin + (center - vmin) * i / half for i in range(half)]
    upper = [center + (vmax - center) * i / half for i in range(half + 1)]
    return cm.LinearColormap(
        colors=DIVERGING_COLORS,
        index=lower + upper,
        vmin=vmin,
        vmax=vmax,
    )


def _compute_centroid(coordinates: list) -> tuple[float, float]:
    """
    폴리곤 좌표에서 대략적인 중심점을 계산한다.
    GeoJSON 좌표는 [경도, 위도] 순서이므로 반전하여 [위도, 경도]로 반환한다.
    """
    all_points = []

    def _flatten(coords):
        """중첩된 좌표 리스트를 평탄화한다."""
        if isinstance(coords[0], (int, float)):
            all_points.append(coords)
        else:
            for c in coords:
                _flatten(c)

    _flatten(coordinates)
    if not all_points:
        return (37.5665, 126.9780)  # 기본값: 서울시청

    avg_lon = sum(p[0] for p in all_points) / len(all_points)
    avg_lat = sum(p[1] for p in all_points) / len(all_points)
    return (avg_lat, avg_lon)


def create_base_map(
    geojson: dict,
    map_center: list | None = None,
    map_zoom: int = 10,
) -> folium.Map:
    """
    데이터 없는 base map을 생성한다.

    타일맵과 fit_bounds만 포함하여 streamlit-folium 컴포넌트 키가
    동일 지역 선택에서는 변하지 않도록 한다. 기간(연도·월)이 바뀌어도
    base map HTML이 동일하므로 사용자의 줌/패닝 상태가 보존된다.

    Args:
        geojson: 필터링된 GeoJSON (FeatureCollection)
        map_center: 지도 중심점 [위도, 경도] (None이면 GeoJSON에서 계산)
        map_zoom: 지도 줌 레벨
    """
    # GeoJSON 중심점 계산
    if map_center is None:
        all_centroids = [
            _compute_centroid(f["geometry"]["coordinates"])
            for f in geojson.get("features", [])
        ]
        if all_centroids:
            map_center = [
                sum(c[0] for c in all_centroids) / len(all_centroids),
                sum(c[1] for c in all_centroids) / len(all_centroids),
            ]
        else:
            map_center = [37.5, 127.0]

    m = folium.Map(
        location=map_center,
        zoom_start=map_zoom,
        tiles=None,
    )

    folium.TileLayer(
        tiles=get_vworld_tiles()["기본지도"],
        attr="V-World",
        name="배경",
        opacity=0.3,
    ).add_to(m)
    _ReadableLabels().add_to(m)

    # 지도 범위를 GeoJSON 영역에 맞춤
    all_centroids = [
        _compute_centroid(f["geometry"]["coordinates"])
        for f in geojson.get("features", [])
    ]
    if all_centroids:
        lats = [c[0] for c in all_centroids]
        lons = [c[1] for c in all_centroids]
        m.fit_bounds(
            [[min(lats), min(lons)], [max(lats), max(lons)]],
            padding=[20, 20],
        )

    return m


def create_data_layer(
    geojson: dict,
    df: pd.DataFrame,
    value_col: str,
    sig_cd_col: str,
    title: str,
    center_mode: str,
    unit: str = "%",
    decimals: int = 1,
) -> folium.FeatureGroup:
    """
    코로플레스 데이터 레이어를 FeatureGroup으로 생성한다.

    st_folium의 feature_group_to_add 파라미터로 전달하면
    base map의 HTML이 변하지 않아 줌/패닝 상태가 보존된다.

    Args:
        geojson: 필터링된 GeoJSON (FeatureCollection)
        df: 지표 데이터 DataFrame
        value_col: 값 컬럼명 (예: "증감률", "전세가율", "거래량")
        sig_cd_col: 지역 식별 컬럼명 (예: "sig_cd", 거래량은 "full_nm")
        title: 지도 제목
        center_mode: 색상 중심 모드 (yoy는 0, direct/count는 중앙값)
        unit: 단위 (예: "%", "건")
        decimals: 라벨 소수점 자릿수 (정수형 값은 0, 비율은 1)

    Returns:
        folium.FeatureGroup 객체
    """
    fg = folium.FeatureGroup(name=title)

    if df.empty:
        return fg

    # 값 매핑 딕셔너리 생성
    value_map = dict(zip(df[sig_cd_col].astype(str), df[value_col]))

    # 색상 스케일 생성
    color_bounds = get_color_scale_bounds(df[value_col], center_mode)
    colormap = (
        _get_colormap(color_bounds[0], color_bounds[1], center=color_bounds[2])
        if color_bounds is not None
        else None
    )

    # GeoJSON 스타일 함수
    def style_function(feature):
        props = feature["properties"]
        val = _get_feature_value(value_map, props)
        if val is not None and colormap is not None:
            try:
                color = colormap(val)
            except (ValueError, KeyError):
                color = "#cccccc"
        else:
            color = "#cccccc"
        return {
            "fillColor": color,
            "color": "#999999",
            "weight": 0.5,
            "fillOpacity": 0.75,
        }

    # 라벨을 숨긴 지역도 마우스를 올려 지역명과 실제 값을 확인할 수 있다.
    display_geojson = {
        **geojson,
        "features": [{**feature, "properties": feature["properties"].copy()}
                     for feature in geojson["features"]],
    }
    for feature in display_geojson["features"]:
        props = feature["properties"]
        value = _get_feature_value(value_map, props)
        props["display_value"] = "자료 없음" if value is None else f"{value:,.{decimals}f}{unit}"
        # 동적 FeatureGroup에서는 Tooltip의 header CSS가 전달되지 않으므로 본문에 적용한다.
        props["display_tooltip"] = (
            '<div class="kb-region-tooltip" style="font-size:11px;line-height:1.4;text-align:left;">'
            f"<strong>{html.escape(props['full_nm'])}</strong><br>"
            f"{html.escape(title)}: {html.escape(props['display_value'])}</div>"
        )

    # 코로플레스 GeoJSON 레이어
    folium.GeoJson(
        display_geojson,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["display_tooltip"],
            labels=False,
        ),
    ).add_to(fg)

    # 시군구 라벨 (중심점에 DivIcon)
    for feature in geojson["features"]:
        props = feature["properties"]
        val = _get_feature_value(value_map, props)
        if val is None:
            continue

        centroid = _compute_centroid(feature["geometry"]["coordinates"])
        display_val = f"{val:.{decimals}f}" if isinstance(val, float) else str(val)
        label_text = f"{html.escape(props['sig_kor_nm'])}\n{display_val}{unit}"
        priority = abs(float(val) - color_bounds[2]) if color_bounds else 0

        folium.Marker(
            location=centroid,
            interactive=False,
            keyboard=False,
            icon=folium.DivIcon(
                html=f"""
                <div class="kb-region-label" data-priority="{priority}" style="
                    visibility: hidden;
                    position: relative;
                    left: 50%;
                    transform: translateX(-50%);
                    width: max-content;
                    font-size: 13px;
                    font-weight: 600;
                    color: #333;
                    text-align: center;
                    white-space: pre-line;
                    line-height: 1.3;
                    text-shadow: 0 0 3px white, 0 0 3px white,
                                 0 0 3px white, 0 0 3px white;
                    pointer-events: none;
                ">{label_text}</div>
                """,
                icon_size=(80, 34),
                icon_anchor=(40, 17),
            ),
        ).add_to(fg)

    return fg


def create_choropleth(
    geojson: dict,
    df: pd.DataFrame,
    value_col: str,
    sig_cd_col: str,
    title: str,
    center_mode: str,
    unit: str = "%",
    map_center: list | None = None,
    map_zoom: int = 10,
    auto_fit: bool = True,
) -> folium.Map:
    """
    코로플레스 지도를 생성한다.

    4개 지표 모두 Diverging 색상(파랑↔흰색↔빨강)을 사용한다.
    증감률은 0 기준, 전세가율·거래량은 중앙값 기준으로 색상을 배분하여
    지역 간 상대적 강도를 직관적으로 비교할 수 있다.

    Args:
        geojson: 필터링된 GeoJSON (FeatureCollection)
        df: 지표 데이터 DataFrame
        value_col: 값 컬럼명 (예: "증감률", "전세가율", "거래량")
        sig_cd_col: 지역 식별 컬럼명 (예: "sig_cd", 거래량은 "full_nm")
        title: 지도 제목
        center_mode: 색상 중심 모드 (yoy는 0, direct/count는 중앙값)
        unit: 단위 (예: "%", "건")
        map_center: 지도 중심점 [위도, 경도]
        map_zoom: 지도 줌 레벨

    Returns:
        folium.Map 객체
    """
    if map_center is None:
        map_center = [37.5, 127.0]

    m = folium.Map(
        location=map_center,
        zoom_start=map_zoom,
        tiles=None,
    )

    # 깨끗한 배경 — 데이터에 집중하기 위해 최소한의 타일 사용
    folium.TileLayer(
        tiles=get_vworld_tiles()["기본지도"],
        attr="V-World",
        name="배경",
        opacity=0.3,
    ).add_to(m)

    if df.empty:
        return m

    # 값 매핑 딕셔너리 생성
    value_map = dict(zip(df[sig_cd_col].astype(str), df[value_col]))

    # 색상 스케일 생성 — 모든 지표에 Diverging 사용
    # 증감률(YoY): 0 기준 대칭 (상승=빨강, 하락=파랑)
    # 전세가율·거래량: 중앙값 기준 대칭 (강=빨강, 약=파랑)
    color_bounds = get_color_scale_bounds(df[value_col], center_mode)
    colormap = (
        _get_colormap(color_bounds[0], color_bounds[1], center=color_bounds[2])
        if color_bounds is not None
        else None
    )

    # GeoJSON 스타일 함수
    def style_function(feature):
        props = feature["properties"]
        val = _get_feature_value(value_map, props)

        if val is not None and colormap is not None:
            try:
                color = colormap(val)
            except (ValueError, KeyError):
                color = "#cccccc"
        else:
            color = "#cccccc"

        return {
            "fillColor": color,
            "color": "#999999",
            "weight": 0.5,
            "fillOpacity": 0.75,
        }

    # 코로플레스 GeoJSON 레이어
    folium.GeoJson(
        geojson,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["sig_kor_nm"],
            aliases=["시군구"],
            style="font-size: 12px;",
        ),
    ).add_to(m)

    # 시군구 라벨 (중심점에 DivIcon)
    for feature in geojson["features"]:
        props = feature["properties"]
        sig_name = props["sig_kor_nm"]
        val = _get_feature_value(value_map, props)

        if val is None:
            continue

        centroid = _compute_centroid(feature["geometry"]["coordinates"])
        label_text = f"{sig_name}\n{val}{unit}"

        folium.Marker(
            location=centroid,
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    font-size: 13px;
                    font-weight: 600;
                    color: #333;
                    text-align: center;
                    white-space: pre-line;
                    line-height: 1.3;
                    text-shadow: 0 0 3px white, 0 0 3px white,
                                 0 0 3px white, 0 0 3px white;
                    pointer-events: none;
                ">{label_text}</div>
                """,
                icon_size=(80, 34),
                icon_anchor=(40, 17),
            ),
        ).add_to(m)

    # 범례 추가
    if colormap is not None:
        colormap.caption = title
        colormap.add_to(m)

    # 지도 범위를 데이터에 맞춤 (auto_fit=False이면 사용자 배율 유지)
    if auto_fit:
        all_centroids = []
        for feature in geojson["features"]:
            centroid = _compute_centroid(feature["geometry"]["coordinates"])
            all_centroids.append(centroid)
        if all_centroids:
            lats = [c[0] for c in all_centroids]
            lons = [c[1] for c in all_centroids]
            m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]], padding=[20, 20])

    return m
