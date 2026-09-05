"""
관심단지 목록 관리 모듈

JSON 파일 기반으로 관심단지 목록을 관리한다.
추가 시 DuckDB 매매 테이블에서 단지 존재 여부를 검증한다.
"""

import json
from pathlib import Path

import duckdb

from src.config import DB_PATH

# ──────────────────────────────────────────────
# 경로 설정
# ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent
WATCHLIST_PATH = Path(__file__).parent / "data" / "watchlist.json"


def _load() -> list[dict]:
    """JSON 파일에서 관심단지 목록을 읽는다."""
    if not WATCHLIST_PATH.exists():
        return []
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(watchlist: list[dict]) -> None:
    """관심단지 목록을 JSON 파일에 저장한다."""
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)


def get_all() -> list[dict]:
    """관심단지 목록 전체를 반환한다."""
    return _load()


def search(단지명: str) -> None:
    """
    매매 테이블에서 단지명을 검색하고, 거래 가능한 전용면적 목록을 보여준다.
    """
    con = duckdb.connect(DB_PATH, read_only=True)
    rows = con.execute("""
        SELECT DISTINCT 시군구, 단지명, 전용면적
        FROM 매매
        WHERE 단지명 LIKE ?
        ORDER BY 시군구, 전용면적
    """, [f"%{단지명}%"]).fetchall()
    con.close()

    if not rows:
        print(f"'{단지명}'에 해당하는 단지를 찾을 수 없습니다.")
        return

    print(f"\n'{단지명}' 검색 결과:\n")
    current_key = None
    for 시군구, name, area in rows:
        key = f"{시군구} {name}"
        if key != current_key:
            current_key = key
            print(f"  [{시군구}] {name}")
        print(f"    - 전용면적: {area}㎡")


def add(단지명: str, 전용면적: float) -> None:
    """
    관심단지를 추가한다.
    매매 테이블에서 해당 단지·면적의 존재 여부를 확인한 후 추가한다.
    """
    con = duckdb.connect(DB_PATH, read_only=True)

    # 단지명 + 면적으로 정확히 매칭되는 거래 확인
    rows = con.execute("""
        SELECT DISTINCT 시군구, 단지명, 전용면적
        FROM 매매
        WHERE 단지명 = ? AND ABS(전용면적 - ?) < 1
        ORDER BY 시군구
    """, [단지명, 전용면적]).fetchall()
    con.close()

    if not rows:
        print(f"'{단지명}' (전용면적 {전용면적}㎡)에 해당하는 거래 내역이 없습니다.")
        print("단지명을 정확히 입력했는지 확인하세요. search() 함수로 검색해볼 수 있습니다.")
        return

    # 여러 지역에 동일 단지명이 있으면 모두 표시
    if len(set(r[0] for r in rows)) > 1:
        print(f"'{단지명}'이(가) 여러 지역에 있습니다:")
        for 시군구, _, area in rows:
            print(f"  - {시군구} (전용면적: {area}㎡)")
        print("시군구를 포함해서 다시 추가해주세요.")
        return

    시군구 = rows[0][0]
    actual_area = rows[0][2]

    # 중복 확인
    watchlist = _load()
    for item in watchlist:
        if item["단지명"] == 단지명 and abs(item["전용면적"] - actual_area) < 1:
            print(f"이미 등록된 단지입니다: {단지명} ({actual_area}㎡)")
            return

    # 추가
    watchlist.append({
        "시군구": 시군구,
        "단지명": 단지명,
        "전용면적": actual_area,
    })
    _save(watchlist)
    print(f"추가 완료: [{시군구}] {단지명} ({actual_area}㎡)")


def remove(단지명: str, 전용면적: float) -> None:
    """관심단지를 삭제한다."""
    watchlist = _load()
    before = len(watchlist)
    watchlist = [
        item for item in watchlist
        if not (item["단지명"] == 단지명 and abs(item["전용면적"] - 전용면적) < 1)
    ]
    _save(watchlist)

    if len(watchlist) < before:
        print(f"삭제 완료: {단지명} ({전용면적}㎡)")
    else:
        print(f"'{단지명}' ({전용면적}㎡)을(를) 찾을 수 없습니다.")


def show() -> None:
    """관심단지 전체 목록을 출력한다."""
    watchlist = _load()
    if not watchlist:
        print("등록된 관심단지가 없습니다.")
        return

    print(f"\n관심단지 목록 ({len(watchlist)}건):\n")
    for i, item in enumerate(watchlist, 1):
        print(f"  {i}. [{item['시군구']}] {item['단지명']} ({item['전용면적']}㎡)")


if __name__ == "__main__":
    show()
