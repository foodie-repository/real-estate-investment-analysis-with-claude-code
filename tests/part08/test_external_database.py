import duckdb


def _create_external_schema_db(path):
    con = duckdb.connect(str(path))
    try:
        con.execute(
            '''
            CREATE TABLE 매매 (
                시군구 VARCHAR,
                번지 VARCHAR,
                단지명 VARCHAR,
                "전용면적(㎡)" DOUBLE,
                계약년월 INTEGER,
                건축년도 INTEGER,
                도로명 VARCHAR,
                해제사유발생일 VARCHAR,
                시도 VARCHAR,
                읍면동 VARCHAR,
                리 VARCHAR
            )
            '''
        )
        con.executemany(
            'INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                ('해운대구', '123', '테스트단지', 84.9, 202501, 2015, '해운대로 1', None, '부산광역시', '우동', ''),
                ('성남시 분당구', '456', '판교단지', 59.9, 202501, 2020, '판교로 1', None, '경기도', '백현동', ''),
                ('세종시', '1277', '대우푸르지오(10단지)', 84.9, 202501, 2014, '아름로 1', None, '세종특별자치시', '아름동', ''),
                ('세종시', '가-', '산울마을5단지', 59.9, 202501, 2023, '산울로 5', None, '세종특별자치시', '산울동', ''),
                ('세종시', '89', '욱일아파트', 59.9, 202501, 1996, '침산로 1', None, '세종특별자치시', '조치원읍', '침산리'),
            ],
        )
        con.execute(
            '''
            CREATE TABLE 좌표 (
                도로명주소 VARCHAR,
                경도 DOUBLE,
                위도 DOUBLE,
                수집일시 TIMESTAMP
            )
            '''
        )
        con.executemany(
            'INSERT INTO 좌표 VALUES (?, ?, ?, now())',
            [
                ('부산광역시 해운대구 해운대로 1', 129.16, 35.16),
                ('경기도 성남시 판교로 1', 127.11, 37.39),
                ('세종특별자치시 세종시 아름로 1', 127.25, 36.51),
                ('세종특별자치시 세종시 산울로 5', 127.26, 36.53),
                ('세종특별자치시 세종시 침산로 1', 127.29, 36.60),
            ],
        )
        con.execute(
            '''
            CREATE TABLE 공동주택_전국 (
                주소 VARCHAR,
                단지명 VARCHAR,
                단지명_공시가격 VARCHAR,
                단지명_건축물대장 VARCHAR,
                단지명_도로명주소 VARCHAR,
                단지구분코드 VARCHAR,
                세대수 INTEGER
            )
            '''
        )
        con.executemany(
            'INSERT INTO 공동주택_전국 VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
                ('부산광역시 해운대구 우동 123', '테스트단지', '테스트단지', '테스트단지', '테스트단지', '1', 500),
                ('경기도 성남시 분당구 백현동 456', '판교단지', '판교단지', '판교단지', '판교단지', '1', 700),
                (
                    '세종특별자치시  아름동 1277',
                    '범지기마을10단지(대우푸르지오) 범지기마을 10단지 범지기마을 10단지',
                    '범지기마을10단지(대우푸르지오)',
                    '범지기마을 10단지',
                    '범지기마을 10단지',
                    '1',
                    1970,
                ),
                (
                    '세종특별자치시  산울동 가-',
                    '산울마을5단지 산울마을5단지 산울마을5단지',
                    '산울마을5단지',
                    '산울마을5단지',
                    '산울마을5단지',
                    '1',
                    995,
                ),
                (
                    '세종특별자치시  조치원읍 침산리 89',
                    '욱일1차 욱일아파트 욱일아파트',
                    '욱일1차',
                    '욱일아파트',
                    '욱일아파트',
                    '1',
                    1208,
                ),
            ],
        )
    finally:
        con.close()


def test_trade_map_database_path_honors_environment_override(tmp_path, monkeypatch):
    from projects.chapter08_trade_map.dashboard.db import database_path

    db_path = tmp_path / 'external.duckdb'
    _create_external_schema_db(db_path)
    monkeypatch.setenv('TRADE_MAP_DB_PATH', str(db_path))

    assert database_path() == db_path


def test_region_options_support_separated_full_database_schema(tmp_path, monkeypatch):
    from projects.chapter08_trade_map.dashboard.preprocessing import get_region_options

    db_path = tmp_path / 'external.duckdb'
    _create_external_schema_db(db_path)
    monkeypatch.setenv('TRADE_MAP_DB_PATH', str(db_path))

    regions = get_region_options('매매')

    assert sorted(regions) == ['경기도', '부산광역시', '세종특별자치시']
    assert regions['부산광역시']['해운대구'] == ['우동']
    assert regions['경기도']['성남시 분당구'] == ['백현동']
    assert regions['세종특별자치시']['세종시'] == ['산울동', '아름동', '조치원읍 침산리']


def test_pivot_supports_separated_full_database_schema(tmp_path, monkeypatch):
    from projects.chapter08_trade_map.dashboard.pivot import generate_pivot_table

    db_path = tmp_path / 'external.duckdb'
    _create_external_schema_db(db_path)
    monkeypatch.setenv('TRADE_MAP_DB_PATH', str(db_path))

    result = generate_pivot_table(
        거래유형='매매',
        시도='부산광역시',
        시군구='해운대구',
        연도_시작=2025,
        연도_끝=2025,
    )

    assert result[['시도', '시군구', '읍면동', '단지명']].to_dict('records') == [
        {'시도': '부산광역시', '시군구': '해운대구', '읍면동': '우동', '단지명': '테스트단지'},
    ]
    assert result.iloc[0]['거래량'] == 1
    assert result.iloc[0]['세대수'] == 500
    assert result.iloc[0]['경도'] == 129.16
    assert result.iloc[0]['위도'] == 35.16


def test_pivot_matches_sejong_households_with_source_address_and_name_variants(
    tmp_path, monkeypatch
):
    """세종의 빈 시군구·중복 공백·가- 지번·공식 단지명 변형을 함께 처리한다."""
    from projects.chapter08_trade_map.dashboard.pivot import generate_pivot_table

    db_path = tmp_path / 'external.duckdb'
    _create_external_schema_db(db_path)
    monkeypatch.setenv('TRADE_MAP_DB_PATH', str(db_path))

    result = generate_pivot_table(
        거래유형='매매',
        시도='세종특별자치시',
        시군구='세종시',
        연도_시작=2025,
        연도_끝=2025,
    )

    households = result.set_index('단지명')['세대수'].to_dict()
    assert households == {
        '대우푸르지오(10단지)': 1970,
        '산울마을5단지': 995,
        '욱일아파트': 1208,
    }
    assert result['회전율'].notna().all()
