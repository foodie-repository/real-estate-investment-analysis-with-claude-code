"""
시군구 경계지도 수집 모듈

V-World 2D Data API로 전국 시군구 행정구역 경계를 수집하여
GeoJSON 파일로 저장한다.

사용법:
    python -m src.collectors.경계지도
"""

import json
import sys
import time
from pathlib import Path

import requests

from src.config import VWORLD_API_KEY

# ──────────────────────────────────────────────
# 경로 설정
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "boundaries" / "시군구.geojson"

# ──────────────────────────────────────────────
# API 설정
# ──────────────────────────────────────────────
DATA_URL = "https://api.vworld.kr/req/data"
DATA_LAYER = "LT_C_ADSIGG_INFO"
DOMAIN = "localhost"  # 키 발급 시 등록한 도메인
BBOX = "BOX(124.6,33.1,131.9,38.6)"  # 전국 영역 (WGS84)
PAGE_SIZE = 100  # 1회 최대 요청 건수


def fetch_page(page: int) -> dict:
    """
    V-World Data API에서 한 페이지 분량의 시군구 경계를 가져온다.

    Args:
        page: 페이지 번호 (1부터 시작)

    Returns:
        API 응답 dict
    """
    params = {
        "service": "data",
        "request": "GetFeature",
        "data": DATA_LAYER,
        "key": VWORLD_API_KEY,
        "domain": DOMAIN,
        "geomFilter": BBOX,
        "crs": "EPSG:4326",
        "format": "json",
        "page": page,
        "size": PAGE_SIZE,
    }
    resp = requests.get(DATA_URL, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def collect_all() -> list[dict]:
    """
    페이징 처리를 통해 전국 시군구 경계 전체를 수집한다.

    Returns:
        GeoJSON Feature 리스트
    """
    all_features = []
    page = 1

    while True:
        print(f"  페이지 {page} 요청 중...", end=" ", flush=True)
        data = fetch_page(page)

        response = data.get("response", {})
        if response.get("status") != "OK":
            err = response.get("error", {})
            raise RuntimeError(f"API 오류: {err.get('code')} - {err.get('text')}")

        features = (
            response.get("result", {}).get("featureCollection", {}).get("features", [])
        )
        count = len(features)
        print(f"{count}건 수신")

        if count == 0:
            break

        all_features.extend(features)

        # PAGE_SIZE보다 적게 왔으면 마지막 페이지
        if count < PAGE_SIZE:
            break

        page += 1
        time.sleep(0.2)  # API 부하 방지

    return all_features


def save_geojson(features: list[dict]) -> None:
    """
    수집된 Feature 목록을 GeoJSON FeatureCollection으로 저장한다.

    Args:
        features: GeoJSON Feature 리스트
    """
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    size_mb = OUTPUT_PATH.stat().st_size / 1024 / 1024
    print(f"\n  저장 완료: {OUTPUT_PATH}")
    print(f"  파일 크기: {size_mb:.1f} MB")


def verify(features: list[dict]) -> None:
    """수집된 데이터를 검증하여 요약 정보를 출력한다."""
    print(f"\n=== 수집 결과 검증 ===")
    print(f"  총 시군구 수: {len(features)}개")

    if not features:
        print("  ⚠️  데이터 없음")
        return

    # 속성 확인
    sample = features[0].get("properties", {})
    print(f"  속성 키: {list(sample.keys())}")

    # 시도별 집계
    sido_count: dict[str, int] = {}
    for f in features:
        full_nm = f.get("properties", {}).get("full_nm", "")
        sido = full_nm.split()[0] if full_nm else "알 수 없음"
        sido_count[sido] = sido_count.get(sido, 0) + 1

    print(f"\n  시도별 시군구 수:")
    for sido, cnt in sorted(sido_count.items()):
        print(f"    {sido}: {cnt}개")


def main():
    print("=" * 60)
    print("시군구 경계지도 수집 (V-World 2D Data API)")
    print("=" * 60)

    if not VWORLD_API_KEY:
        print("오류: .env 파일에 VWORLD_API_KEY를 설정하세요.")
        sys.exit(1)

    print(f"  레이어: {DATA_LAYER}")
    print(f"  저장 경로: {OUTPUT_PATH}")
    print(f"  좌표계: EPSG:4326 (WGS84)")
    print()

    # 수집
    print("[1/2] 경계 데이터 수집 중...")
    features = collect_all()

    if not features:
        print("오류: 수집된 데이터가 없습니다.")
        sys.exit(1)

    # 저장
    print("\n[2/2] GeoJSON 파일 저장 중...")
    save_geojson(features)

    # 검증
    verify(features)

    print("\n완료!")


if __name__ == "__main__":
    main()
