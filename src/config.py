"""
프로젝트 공통 설정 모듈

DB 경로, API 키 등 전역 설정값을 한 곳에서 관리한다.
모든 수집 모듈과 미니 프로젝트는 이 파일에서 설정을 가져다 쓴다.
"""

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# ──────────────────────────────────────────────
# 경로 설정
# ──────────────────────────────────────────────
# 프로젝트 루트: src/ 의 상위 디렉토리
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# .env 파일에서 환경변수 로드
load_dotenv(PROJECT_ROOT / ".env")

# DuckDB 파일 경로
DB_PATH = str(PROJECT_ROOT / "data" / "apt_investment.duckdb")

# 현재 연도 (연식 계산 기준)
CURRENT_YEAR: int = date.today().year

# ──────────────────────────────────────────────
# API 키
# ──────────────────────────────────────────────
# 공공데이터포털 API 키 (실거래가, 공동주택 기본정보)
PUBLIC_DATA_API_KEY = os.getenv("PUBLIC_DATA_API_KEY")

# 카카오 REST API 키 (Geocoding)
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY")

# V-World API 키 (시군구 경계지도 WFS)
VWORLD_API_KEY = os.getenv("VWORLD_API_KEY")

# ──────────────────────────────────────────────
# V-World 지도 타일 설정 (Part08~09 대시보드용)
# ──────────────────────────────────────────────
def get_vworld_tiles() -> dict:
    """V-World 타일 URL 딕셔너리를 반환한다.

    .env에 VWORLD_API_KEY가 없으면 EnvironmentError를 발생시킨다.
    임포트 시점이 아닌 실제 사용 시점에 키 유무를 검증하기 위해 함수로 제공한다.
    """
    key = os.getenv("VWORLD_API_KEY")
    if not key:
        raise EnvironmentError(
            ".env 파일에 VWORLD_API_KEY가 설정되지 않았습니다.\n"
            "  VWORLD_API_KEY=발급받은키  형태로 추가하세요."
        )
    return {
        "기본지도": f"https://api.vworld.kr/req/wmts/1.0.0/{key}/Base/{{z}}/{{y}}/{{x}}.png",
        "위성지도": f"https://api.vworld.kr/req/wmts/1.0.0/{key}/Satellite/{{z}}/{{y}}/{{x}}.jpeg",
        "하이브리드": f"https://api.vworld.kr/req/wmts/1.0.0/{key}/Hybrid/{{z}}/{{y}}/{{x}}.png",
    }

# 기본 지도 중심점 (서울시청)
DEFAULT_MAP_CENTER = [37.5665, 126.9780]
DEFAULT_MAP_ZOOM = 12
