import duckdb


def _create_price_volume_db(db_path):
    con = duckdb.connect(str(db_path))
    try:
        con.execute("""
            CREATE TABLE 매매 (
                시군구 VARCHAR,
                단지명 VARCHAR,
                전용면적 DOUBLE,
                거래금액 BIGINT,
                계약년월 INTEGER,
                층 INTEGER,
                건축년도 INTEGER,
                도로명 VARCHAR,
                해제사유발생일 VARCHAR,
                거래유형 VARCHAR
            )
        """)
        con.execute("""
            CREATE TABLE 전월세 (
                시군구 VARCHAR,
                단지명 VARCHAR,
                전월세구분 VARCHAR,
                전용면적 DOUBLE,
                보증금 BIGINT,
                계약년월 INTEGER,
                층 INTEGER,
                건축년도 INTEGER,
                도로명 VARCHAR
            )
        """)
        con.executemany(
            "INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("서울특별시 강남구 역삼동", "테스트단지", 84.0, 100000, 202501, 10, 2010, "테스트로 1", None, "중개거래"),
                ("서울특별시 강남구 역삼동", "직거래단지", 84.0, 90000, 202501, 3, 2010, "테스트로 2", None, "직거래"),
                ("서울특별시 강남구 역삼동", "취소단지", 84.0, 80000, 202501, 4, 2010, "테스트로 3", "20250120", "중개거래"),
            ],
        )
        con.executemany(
            "INSERT INTO 전월세 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("서울특별시 강남구 역삼동", "테스트단지", "전세", 84.0, 60000, 202501, 5, 2010, "테스트로 1"),
                ("서울특별시 강남구 역삼동", "월세단지", "월세", 84.0, 10000, 202501, 2, 2010, "테스트로 4"),
            ],
        )
    finally:
        con.close()


def test_individual_and_monthly_queries_keep_expected_outputs(tmp_path, monkeypatch):
    from projects.part10_price_volume.dashboard import db, preprocessing

    db_path = tmp_path / "price_volume.duckdb"
    _create_price_volume_db(db_path)
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))

    params = dict(
        시도="서울특별시",
        시군구="강남구",
        읍면동=["역삼동"],
        단지=None,
        거래유형="매매+전세",
        평형대=["30평대"],
        시작년월=202501,
        종료년월=202501,
    )

    individual = preprocessing.get_individual_trades(**params)
    monthly = preprocessing.get_monthly_summary(**params)

    assert list(individual.keys()) == ["매매", "전세"]
    assert individual["매매"].iloc[0]["단지명"] == "테스트단지"
    assert individual["매매"].iloc[0]["가격_억"] == 10.0
    assert individual["매매"].iloc[0]["평형대"] == "30평대"
    assert individual["전세"].iloc[0]["가격_억"] == 6.0

    assert monthly["매매"].iloc[0]["중위가_억"] == 10.0
    assert monthly["매매"].iloc[0]["거래량"] == 1
    assert monthly["전세"].iloc[0]["중위가_억"] == 6.0
    assert monthly["전세"].iloc[0]["거래량"] == 1


def test_summary_stats_excludes_direct_and_cancelled_trades(tmp_path, monkeypatch):
    from projects.part10_price_volume.dashboard import db, preprocessing

    db_path = tmp_path / "price_volume.duckdb"
    _create_price_volume_db(db_path)
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))

    stats = preprocessing.get_summary_stats(
        시도="서울특별시",
        시군구="강남구",
        읍면동=["역삼동"],
        평형대=["30평대"],
        시작년월=202501,
        종료년월=202501,
    )

    assert stats["총거래건수"] == 1
    assert stats["최고가_억"] == 10.0
    assert stats["최저가_억"] == 10.0
    assert stats["최근거래"].iloc[0]["단지명"] == "테스트단지"
