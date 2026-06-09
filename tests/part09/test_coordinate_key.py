"""
좌표 수집과 Part09 조인이 도로명주소 키를 일관되게 쓰는지 검증한다.

전국 데이터에서는 같은 도로명이 서로 다른 지역에 반복될 수 있으므로,
도로명 단독 조인은 오좌표를 만들 수 있다.
"""

import importlib

import duckdb


def _create_coordinate_key_db(db_path, include_region_qualified_coordinates=True):
    con = duckdb.connect(str(db_path))
    try:
        con.execute("""
            CREATE TABLE 매매 (
                시군구 VARCHAR,
                단지명 VARCHAR,
                전용면적 DOUBLE,
                계약년월 INTEGER,
                건축년도 INTEGER,
                도로명 VARCHAR,
                거래금액 BIGINT,
                해제사유발생일 VARCHAR,
                거래유형 VARCHAR
            )
        """)
        con.execute("""
            CREATE TABLE 전월세 (
                시군구 VARCHAR,
                단지명 VARCHAR,
                전용면적 DOUBLE,
                계약년월 INTEGER,
                건축년도 INTEGER,
                도로명 VARCHAR,
                전월세구분 VARCHAR,
                보증금 BIGINT
            )
        """)
        con.execute("""
            CREATE TABLE 좌표 (
                도로명주소 VARCHAR,
                경도 DOUBLE,
                위도 DOUBLE
            )
        """)
        con.execute("""
            CREATE TABLE 공동주택_전국 (
                주소 VARCHAR,
                단지명 VARCHAR,
                세대수 INTEGER,
                단지구분코드 VARCHAR
            )
        """)
        con.executemany(
            "INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("서울특별시 강남구 역삼동", "강남단지", 84.0, 202501, 2010, "같은로 1", 100000, None, "중개거래"),
                ("서울특별시 서초구 서초동", "서초단지", 84.0, 202501, 2011, "같은로 1", 110000, None, "중개거래"),
                ("서울특별시 송파구 가락동", "송파단지", 84.0, 202501, 2012, "유일로 1", 120000, None, "중개거래"),
            ],
        )
        coordinates = [
            ("같은로 1", 999.0, 999.0),
            ("유일로 1", 129.0, 39.0),
        ]
        if include_region_qualified_coordinates:
            coordinates.extend([
                ("서울특별시 강남구 같은로 1", 127.0, 37.0),
                ("서울특별시 서초구 같은로 1", 128.0, 38.0),
            ])
        con.executemany("INSERT INTO 좌표 VALUES (?, ?, ?)", coordinates)
        con.executemany(
            "INSERT INTO 공동주택_전국 VALUES (?, ?, ?, ?)",
            [
                ("서울특별시 강남구 역삼동 1", "강남단지", 100, "1"),
                ("서울특별시 서초구 서초동 1", "서초단지", 100, "1"),
                ("서울특별시 송파구 가락동 1", "송파단지", 100, "1"),
            ],
        )
    finally:
        con.close()


def test_coordinate_collector_builds_region_qualified_keys(tmp_path, monkeypatch):
    collector = importlib.import_module("src.collectors.좌표")

    db_path = tmp_path / "coordinate_key.duckdb"
    _create_coordinate_key_db(db_path, include_region_qualified_coordinates=False)
    monkeypatch.setattr(collector, "DB_PATH", str(db_path))

    addresses = collector.get_addresses_to_geocode()

    assert "서울특별시 강남구 같은로 1" in addresses
    assert "서울특별시 서초구 같은로 1" in addresses
    assert "서울특별시 송파구 유일로 1" in addresses
    assert "같은로 1" not in addresses


def test_coordinate_collector_backfills_only_unambiguous_legacy_coordinates(tmp_path, monkeypatch):
    collector = importlib.import_module("src.collectors.좌표")

    db_path = tmp_path / "coordinate_backfill.duckdb"
    _create_coordinate_key_db(db_path, include_region_qualified_coordinates=False)
    monkeypatch.setattr(collector, "DB_PATH", str(db_path))

    inserted = collector.backfill_region_qualified_coordinates_from_legacy()

    assert inserted == 1

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute("""
            SELECT 도로명주소, 경도, 위도
            FROM 좌표
            ORDER BY 도로명주소
        """).fetchall()
    finally:
        con.close()

    assert ("서울특별시 송파구 유일로 1", 129.0, 39.0) in rows
    assert ("서울특별시 강남구 같은로 1", 999.0, 999.0) not in rows
    assert ("서울특별시 서초구 같은로 1", 999.0, 999.0) not in rows


def test_part09_pivot_joins_coordinates_by_region_qualified_key(tmp_path, monkeypatch):
    from projects.part09_trade_map.dashboard import db
    from projects.part09_trade_map.dashboard.pivot import generate_pivot_table

    db_path = tmp_path / "coordinate_key.duckdb"
    _create_coordinate_key_db(db_path)
    monkeypatch.setattr(db, "DB_PATH", str(db_path))

    df = generate_pivot_table(
        거래유형="매매",
        시도="서울특별시",
        시군구=["강남구", "서초구"],
        연도_시작=2025,
        연도_끝=2025,
    )

    coords = {
        row["단지명"]: (row["경도"], row["위도"])
        for _, row in df.iterrows()
    }
    assert coords["강남단지"] == (127.0, 37.0)
    assert coords["서초단지"] == (128.0, 38.0)


def test_shared_trade_preprocessing_joins_coordinates_by_region_qualified_key(tmp_path):
    from src.preprocessing.trade import preprocess

    db_path = tmp_path / "coordinate_key.duckdb"
    _create_coordinate_key_db(db_path)

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        df = preprocess("매매", steps=["좌표연결"], con=con).df()
    finally:
        con.close()

    coords = {
        row["단지명"]: (row["경도"], row["위도"])
        for _, row in df.iterrows()
    }
    assert coords["강남단지"] == (127.0, 37.0)
    assert coords["서초단지"] == (128.0, 38.0)
