"""
Folium 코로플레스 지도 빌더

시군구 경계 GeoJSON 위에 지표 값을 색상으로 채워 코로플레스 맵을 생성한다.
"""
import folium
import branca.colormap as cm
import pandas as pd

from projects.part08_kb_dashboard.dashboard.constants import DIVERGING_COLORS


def _get_colormap(
    vmin: float, vmax: float, center: float = 0.0,
) -> cm.LinearColormap:
    """
    Diverging colormap을 생성한다 (파랑↔흰색↔빨강).

    center를 기준으로 대칭 범위를 설정하여
    center보다 낮으면 파랑, 높으면 빨강, 같으면 흰색으로 표현한다.

    Args:
        vmin: 데이터 최솟값
        vmax: 데이터 최댓값
        center: 색상 중심값 (증감률은 0, 전세가율·거래량은 중앙값)
    """
    # center 기준 대칭 범위
    abs_max = max(abs(vmin - center), abs(vmax - center))
    return cm.LinearColormap(
        colors=DIVERGING_COLORS,
        vmin=center - abs_max,
        vmax=center + abs_max,
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
        tiles="cartodbpositron",
        attr="CartoDB",
        name="배경",
        opacity=0.3,
    ).add_to(m)

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
        sig_cd_col: sig_cd 컬럼명 (예: "sig_cd", 거래량은 "sig_kor_nm")
        title: 지도 제목
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
    vmin = float(df[value_col].min())
    vmax = float(df[value_col].max())
    center = 0.0 if vmin < 0 else float(df[value_col].median())
    colormap = _get_colormap(vmin, vmax, center=center)

    # GeoJSON 스타일 함수
    def style_function(feature):
        props = feature["properties"]
        val = value_map.get(props["sig_cd"], value_map.get(props["sig_kor_nm"]))
        if val is not None:
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
    ).add_to(fg)

    # 시군구 라벨 (중심점에 DivIcon)
    for feature in geojson["features"]:
        props = feature["properties"]
        val = value_map.get(props["sig_cd"], value_map.get(props["sig_kor_nm"]))
        if val is None:
            continue

        centroid = _compute_centroid(feature["geometry"]["coordinates"])
        display_val = f"{val:.{decimals}f}" if isinstance(val, float) else str(val)
        label_text = f"{props['sig_kor_nm']}\n{display_val}{unit}"

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
        ).add_to(fg)

    return fg


def create_choropleth(
    geojson: dict,
    df: pd.DataFrame,
    value_col: str,
    sig_cd_col: str,
    title: str,
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
        sig_cd_col: sig_cd 컬럼명 (예: "sig_cd", 거래량은 "sig_kor_nm")
        title: 지도 제목
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
        tiles="cartodbpositron",
        attr="CartoDB",
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
    vmin = float(df[value_col].min())
    vmax = float(df[value_col].max())
    center = 0.0 if vmin < 0 else float(df[value_col].median())
    colormap = _get_colormap(vmin, vmax, center=center)

    # GeoJSON 스타일 함수
    def style_function(feature):
        props = feature["properties"]
        sig_cd = props["sig_cd"]
        sig_name = props["sig_kor_nm"]

        # sig_cd 또는 sig_kor_nm으로 값 찾기
        val = value_map.get(sig_cd, value_map.get(sig_name))

        if val is not None:
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
        sig_cd = props["sig_cd"]
        sig_name = props["sig_kor_nm"]
        val = value_map.get(sig_cd, value_map.get(sig_name))

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
