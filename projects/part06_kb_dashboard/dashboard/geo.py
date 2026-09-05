"""
GeoJSON 로딩, 매칭, 필터링 모듈

시군구 경계 GeoJSON을 로드하고, KB 지역코드·지역명과 매칭한다.
GeoJSON 속성: sig_cd(5자리), sig_kor_nm(시군구명), full_nm(시도+시군구)
"""
import json

from src.config import PROJECT_ROOT

GEOJSON_PATH = PROJECT_ROOT / "data" / "boundaries" / "시군구.geojson"


def load_geojson() -> dict:
    """시군구 경계 GeoJSON 파일을 로드한다."""
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_lookup(geojson: dict) -> tuple[dict, dict]:
    """
    GeoJSON에서 매칭용 딕셔너리를 생성한다.

    Returns:
        (sig_cd → sig_kor_nm 딕셔너리, sig_kor_nm → sig_cd 딕셔너리)
    """
    code_to_name = {}
    name_to_code = {}
    for feat in geojson["features"]:
        props = feat["properties"]
        code = props["sig_cd"]
        name = props["sig_kor_nm"]
        code_to_name[code] = name
        name_to_code[name] = code
    return code_to_name, name_to_code


def filter_by_sido(geojson: dict, sido_full_names: list[str]) -> dict:
    """
    특정 시도에 해당하는 시군구만 필터링한 GeoJSON을 반환한다.

    Args:
        geojson: 전체 GeoJSON
        sido_full_names: 시도 정식명 목록 (예: ["서울특별시", "경기도"])
    """
    filtered_features = [
        feat for feat in geojson["features"]
        if any(feat["properties"]["full_nm"].startswith(sido) for sido in sido_full_names)
    ]
    return {
        "type": "FeatureCollection",
        "features": filtered_features,
    }


def get_sido_list(geojson: dict) -> list[str]:
    """GeoJSON에서 시도 목록을 추출한다 (full_nm의 첫 번째 공백 전까지)."""
    sido_set = set()
    for feat in geojson["features"]:
        full_nm = feat["properties"]["full_nm"]
        # "서울특별시 종로구" → "서울특별시", "세종특별자치시" → "세종특별자치시"
        parts = full_nm.split(" ")
        sido_set.add(parts[0])
    return sorted(sido_set)


def get_sigungu_list(geojson: dict, sido_full_name: str) -> list[str]:
    """특정 시도에 속하는 시군구명 목록을 반환한다."""
    names = []
    for feat in geojson["features"]:
        props = feat["properties"]
        if props["full_nm"].startswith(sido_full_name):
            names.append(props["sig_kor_nm"])
    return sorted(names)


def get_sig_cd_for_names(geojson: dict, sigungu_names: list[str]) -> list[str]:
    """시군구명 목록에 대응하는 sig_cd 목록을 반환한다."""
    _, name_to_code = build_lookup(geojson)
    return [name_to_code[n] for n in sigungu_names if n in name_to_code]
