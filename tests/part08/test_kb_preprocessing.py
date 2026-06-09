"""
Part08 KB 대시보드 전처리 테스트

독자 환경에서는 사전 계산된 KB_*_YoY 뷰가 없고,
Part04 수집기로 만든 원본 KB 지수 테이블만 있을 수 있다.
"""

import duckdb


def _create_reader_style_kb_db(db_path):
    con = duckdb.connect(str(db_path))
    try:
        con.execute("""
            CREATE TABLE KB_매매가격지수 (
                월간주간구분 VARCHAR,
                매물종별구분 VARCHAR,
                지역코드 VARCHAR,
                지역명 VARCHAR,
                날짜 DATE,
                가격지수 DOUBLE
            )
        """)
        con.executemany(
            "INSERT INTO KB_매매가격지수 VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("월간", "아파트", "1100000000", "서울", "2024-01-01", 100.0),
                ("월간", "아파트", "1100000000", "서울", "2025-01-01", 105.0),
                ("월간", "아파트", "1111000000", "종로구", "2024-01-01", 100.0),
                ("월간", "아파트", "1111000000", "종로구", "2025-01-01", 110.0),
            ],
        )
    finally:
        con.close()


def test_yoy_map_data_falls_back_to_raw_kb_index(tmp_path, monkeypatch):
    from projects.part08_kb_dashboard.dashboard import db, preprocessing

    db_path = tmp_path / "reader.duckdb"
    _create_reader_style_kb_db(db_path)
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))

    df = preprocessing.get_yoy_map_data("KB_매매가격지수_YoY", 2025, 1)

    assert len(df) == 1
    assert df.iloc[0]["sig_cd"] == "11110"
    assert df.iloc[0]["지역명"] == "종로구"
    assert df.iloc[0]["증감률"] == 10.0


def test_yoy_timeseries_and_date_range_fall_back_to_raw_kb_index(tmp_path, monkeypatch):
    from projects.part08_kb_dashboard.dashboard import db, preprocessing

    db_path = tmp_path / "reader.duckdb"
    _create_reader_style_kb_db(db_path)
    monkeypatch.setattr(db, "_DB_PATH", str(db_path))

    시군구_df = preprocessing.get_timeseries(
        table="KB_매매가격지수_YoY",
        value_col="가격지수",
        indicator_type="yoy",
        sig_cds=["11110"],
        start_year=2025,
        end_year=2025,
    )
    시도_df = preprocessing.get_timeseries_sido(
        table="KB_매매가격지수_YoY",
        value_col="가격지수",
        indicator_type="yoy",
        sido_names=["서울"],
        start_year=2025,
        end_year=2025,
    )

    assert 시군구_df.iloc[0]["값"] == 10.0
    assert 시도_df.iloc[0]["값"] == 5.0
    assert preprocessing.get_ts_date_range() == (2025, 1, 2025, 1)
