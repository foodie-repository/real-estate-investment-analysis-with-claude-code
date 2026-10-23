import json

import duckdb

from projects.chapter04_tracking import watchlist


def _create_watchlist_db(db_path):
    con = duckdb.connect(str(db_path))
    try:
        con.execute("""
            CREATE TABLE 매매 (
                시군구 VARCHAR,
                단지명 VARCHAR,
                전용면적 DOUBLE
            )
        """)
        con.execute("""
            INSERT INTO 매매 VALUES
            ('서울특별시 강동구 테스트동', '테스트단지', 84.046),
            ('서울특별시 강동구 테스트동', '테스트단지', 84.24),
            ('서울특별시 강동구 테스트동', '테스트단지', 84.3)
        """)
    finally:
        con.close()


def test_add_saves_the_exact_area_selected_by_the_user(tmp_path, monkeypatch):
    """가까운 면적이 먼저 조회돼도 사용자가 선택한 전용면적을 저장한다."""
    db_path = tmp_path / "watchlist.duckdb"
    watchlist_path = tmp_path / "watchlist.json"
    _create_watchlist_db(db_path)
    monkeypatch.setattr(watchlist, "DB_PATH", str(db_path))
    monkeypatch.setattr(watchlist, "WATCHLIST_PATH", watchlist_path)

    watchlist.add("테스트단지", 84.24)

    saved = json.loads(watchlist_path.read_text(encoding="utf-8"))
    assert saved == [
        {
            "시군구": "서울특별시 강동구 테스트동",
            "단지명": "테스트단지",
            "전용면적": 84.24,
        }
    ]


def test_remove_deletes_only_the_exact_area_selected_by_the_user(tmp_path, monkeypatch):
    """같은 단지의 가까운 다른 전용면적은 삭제하지 않는다."""
    watchlist_path = tmp_path / "watchlist.json"
    watchlist_path.write_text(
        json.dumps(
            [
                {
                    "시군구": "서울특별시 강동구 테스트동",
                    "단지명": "테스트단지",
                    "전용면적": 84.24,
                },
                {
                    "시군구": "서울특별시 강동구 테스트동",
                    "단지명": "테스트단지",
                    "전용면적": 84.3,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(watchlist, "WATCHLIST_PATH", watchlist_path)

    watchlist.remove("테스트단지", 84.24)

    saved = json.loads(watchlist_path.read_text(encoding="utf-8"))
    assert saved == [
        {
            "시군구": "서울특별시 강동구 테스트동",
            "단지명": "테스트단지",
            "전용면적": 84.3,
        }
    ]
