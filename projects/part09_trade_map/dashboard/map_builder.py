"""
지도 시각화 모듈

Folium + V-World 타일 + DivIcon 랭킹 원으로
거래량/회전율 랭킹 지도를 생성한다.
"""
import pandas as pd
import folium
from folium import DivIcon
from src.config import get_vworld_tiles, DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM
from projects.part09_trade_map.dashboard.constants import 연식_색상


# 랭킹 원의 고정 크기 (px)
CIRCLE_SIZE = 36


def aggregate_by_complex(df_pivot: pd.DataFrame) -> pd.DataFrame:
    """
    같은 단지의 면적대/연도 행을 합산하여 단지별 1행으로 집계한다.

    좌표 우선순위: 거래량이 가장 많은 행의 좌표를 사용한다.
    """
    # 거래량 내림차순 정렬 → groupby "first"가 가장 많은 거래의 좌표를 사용
    df_sorted = df_pivot.sort_values("거래량", ascending=False)

    agg_dict = {
        "거래량": "sum",
        "경도": "first",
        "위도": "first",
        "건축년도": "first",
        "연식_구분": "first",
    }
    if "세대수" in df_sorted.columns:
        agg_dict["세대수"] = "first"

    df_by_complex = (
        df_sorted
        .groupby(["시도", "시군구", "읍면동", "단지명"], as_index=False)
        .agg(agg_dict)
    )

    # 회전율 재계산 (단지 합산 거래량 / 세대수)
    if "세대수" in df_by_complex.columns:
        mask = df_by_complex["세대수"].notna() & (df_by_complex["세대수"] > 0)
        df_by_complex["회전율"] = None
        df_by_complex.loc[mask, "회전율"] = (
            df_by_complex.loc[mask, "거래량"] * 100.0 / df_by_complex.loc[mask, "세대수"]
        ).round(2)

    return df_by_complex


def create_ranking_map(
    df_pivot: pd.DataFrame,
    랭킹기준: str,
    랭킹개수: int,
    map_style: str = "기본지도",
    center: list | None = None,
    zoom: int | None = None,
) -> folium.Map:
    """
    랭킹 지도를 생성한다.

    Parameters:
        df_pivot: 피벗테이블 DataFrame (경도, 위도, 거래량/회전율 포함)
        랭킹기준: '거래량' 또는 '회전율'
        랭킹개수: 표시할 랭킹 수 (10~50)
        map_style: V-World 지도 스타일
        center: 지도 중심점 [위도, 경도] (None이면 데이터 중심)
        zoom: 줌 레벨 (None이면 기본값)

    Returns:
        folium.Map 객체
    """
    # 단지별 집계
    df_by_complex = aggregate_by_complex(df_pivot)

    # 회전율 기준일 때 NULL 행 제외
    if 랭킹기준 == "회전율":
        df_ranked = df_by_complex.dropna(subset=["회전율"])
    else:
        df_ranked = df_by_complex.copy()

    # 랭킹 기준으로 정렬 후 상위 N개 선택
    df_ranked = df_ranked.sort_values(랭킹기준, ascending=False).head(랭킹개수)
    df_ranked = df_ranked.reset_index(drop=True)

    if df_ranked.empty:
        m = folium.Map(
            location=center or DEFAULT_MAP_CENTER,
            zoom_start=zoom if zoom is not None else DEFAULT_MAP_ZOOM,
            tiles=None,
        )
        _add_vworld_tiles(m, map_style)
        return m

    # 지도 중심점 자동 계산
    if center is None:
        center = [df_ranked["위도"].mean(), df_ranked["경도"].mean()]

    m = folium.Map(
        location=center,
        zoom_start=zoom if zoom is not None else DEFAULT_MAP_ZOOM,
        tiles=None,
    )

    # V-World 타일 추가
    _add_vworld_tiles(m, map_style)

    # 랭킹 원 마커 추가
    for rank, (_, row) in enumerate(df_ranked.iterrows(), start=1):
        연식_구분_val = row["연식_구분"]
        연식_구분 = str(연식_구분_val) if pd.notna(연식_구분_val) else ""
        color = 연식_색상.get(연식_구분, 연식_색상["정보 없음"])

        # 툴팁 HTML
        세대수_text = f"{int(row['세대수']):,}" if pd.notna(row.get("세대수")) else "정보 없음"
        회전율_text = f"{row['회전율']:.2f}%" if pd.notna(row.get("회전율")) else "정보 없음"

        tooltip_html = f"""
        <div style="font-size:13px; line-height:1.6;">
            <b>{row['단지명']}</b><br>
            {row['시도']} {row['시군구']} {row['읍면동']}<br>
            건축년도: {int(row['건축년도'])}년 ({연식_구분})<br>
            거래량: <b>{int(row['거래량']):,}건</b><br>
            세대수: {세대수_text}<br>
            회전율: {회전율_text}
        </div>
        """

        # 원 안에 랭킹 숫자를 표시하는 DivIcon
        icon_html = f"""
        <div style="
            background-color: {color};
            border: 2px solid white;
            border-radius: 50%;
            width: {CIRCLE_SIZE}px;
            height: {CIRCLE_SIZE}px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: bold;
            color: white;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        ">{rank}</div>
        """

        folium.Marker(
            location=[row["위도"], row["경도"]],
            icon=DivIcon(
                html=icon_html,
                icon_size=(CIRCLE_SIZE, CIRCLE_SIZE),
                icon_anchor=(CIRCLE_SIZE // 2, CIRCLE_SIZE // 2),
            ),
            tooltip=folium.Tooltip(tooltip_html),
        ).add_to(m)

    # 마커 영역에 자동 줌 (모든 마커가 보이는 범위)
    bounds = [
        [df_ranked["위도"].min(), df_ranked["경도"].min()],
        [df_ranked["위도"].max(), df_ranked["경도"].max()],
    ]
    m.fit_bounds(bounds, padding=[20, 20])

    return m


def _add_vworld_tiles(m: folium.Map, style: str) -> None:
    """V-World 타일 레이어를 지도에 추가한다."""
    tiles = get_vworld_tiles()
    tile_url = tiles.get(style, tiles["기본지도"])
    folium.TileLayer(
        tiles=tile_url,
        attr="V-World",
        name=style,
    ).add_to(m)
