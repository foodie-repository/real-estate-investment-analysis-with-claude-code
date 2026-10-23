"""7장 선택 → 9장 상세 조회의 대상과 상태 보존을 검증한다."""
from urllib.parse import parse_qs, urlsplit

import duckdb
import pytest

from src.utils.dashboard_link import encode_selection, decode_selection, selection_url
from projects.chapter09_price_volume.dashboard.linked import load_linked_data


TARGETS = [
    ('서울특별시', '강남구', '역삼동', '가상A', '서울특별시 강남구 역삼동 1', '20평대'),
    ('경기도', '성남시 분당구', '정자동', '가상B', '경기도 성남시 분당구 정자동 2', '30평대'),
]


def make_db(path):
    con = duckdb.connect(str(path))
    con.execute('''CREATE TABLE 매매(시군구 VARCHAR, 단지명 VARCHAR, 전용면적 DOUBLE,
        거래금액 BIGINT, 계약년월 INTEGER, 층 INTEGER, 건축년도 INTEGER,
        도로명 VARCHAR, 지번 VARCHAR, 거래유형 VARCHAR, 해제사유발생일 VARCHAR)''')
    con.execute('''CREATE TABLE 전월세(시군구 VARCHAR, 단지명 VARCHAR, 전용면적 DOUBLE,
        보증금 BIGINT, 계약년월 INTEGER, 층 INTEGER, 건축년도 INTEGER,
        도로명 VARCHAR, 지번 VARCHAR, 전월세구분 VARCHAR, 계약구분 VARCHAR)''')
    for region, name, lot in [('서울특별시 강남구 역삼동', '가 상A', '0001-0'),
                              ('경기도 성남시 분당구 정자동', '가상B', '2'),
                              ('서울특별시 강남구 역삼동', '가상A', '99')]:
        for area in [59., 84.]:
            for month, price in [(202401, 60000), (202501, 70000)]:
                con.execute("INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, 10, 2010, '가상로 1', ?, '중개거래', NULL)",
                            [region, name, area, price, month, lot])
                con.execute("INSERT INTO 전월세 VALUES (?, ?, ?, ?, ?, 10, 2010, '가상로 1', ?, '전세', '신규')",
                            [region, name, area, price/2, month, lot])
    con.execute("INSERT INTO 매매 VALUES ('서울특별시 강남구 역삼동','가상A',59,90000,202501,10,2010,'가상로 1','1','중개거래','20250130')")
    con.execute("INSERT INTO 전월세 VALUES ('서울특별시 강남구 역삼동','가상A',59,20000,202501,10,2010,'가상로 1','1','전세','갱신')")
    con.close()


def payload(targets=TARGETS):
    return dict(targets=targets, area=(55., 90.), period=(202501, 202503), floor=(5, 15))


def test_link_roundtrip_deduplicates_and_preserves_pairs():
    token = encode_selection(**payload(TARGETS + TARGETS[:1]))
    decoded = decode_selection(token)
    assert decoded['targets'] == TARGETS
    assert decoded['area'] == (55., 90.)
    url = selection_url('http://localhost:8529/?theme=light', token)
    assert parse_qs(urlsplit(url).query)['selection'] == [token]
    assert parse_qs(urlsplit(url).query)['theme'] == ['light']


@pytest.mark.parametrize('token', ['', 'invalid!', 'a'*20000])
def test_invalid_links_fail_closed(token):
    with pytest.raises(ValueError):
        decode_selection(token)


def test_link_rejects_empty_too_many_and_unsafe_destination():
    with pytest.raises(ValueError):
        encode_selection(**payload([]))
    with pytest.raises(ValueError):
        encode_selection(**payload([(*TARGETS[0][:3], f'A{i}', TARGETS[0][4], '20평대') for i in range(11)]))
    with pytest.raises(ValueError):
        selection_url('javascript:alert(1)', 'test')


def test_exact_pairs_addresses_area_and_monthly_totals(tmp_path):
    path = tmp_path/'link.duckdb'
    make_db(path)
    result = load_linked_data(path, TARGETS, (55., 90.), (202401, 202512), '매매+전세', False)
    assert result['missing'] == []
    assert result['stats']['총거래건수'] == 4
    assert result['individual']['매매']['가격_억'].tolist() == [6., 6., 7., 7.]
    assert set(result['individual']['매매']['평형대']) == {'20평대','30평대'}
    assert result['monthly']['매매']['비교대상'].nunique() == 2
    assert result['monthly']['매매']['거래량'].sum() == 4
    assert result['monthly']['전세']['거래량'].sum() == 5  # 9장에는 갱신도 포함
    narrow = load_linked_data(path, TARGETS, (83., 85.), (202501,202501), '매매만', False)
    assert narrow['stats']['총거래건수'] == 1
    assert narrow['missing'] == [TARGETS[0]]
    assert len(narrow['individual']['매매']) == 1


def test_missing_target_and_empty_selection_never_expand_scope(tmp_path):
    path = tmp_path/'link.duckdb'
    make_db(path)
    absent = (*TARGETS[0][:4], '서울특별시 강남구 역삼동 999', '20평대')
    result = load_linked_data(path, [absent], None, (202401,202512), '매매+전세', False)
    assert result['missing'] == [absent]
    assert result['stats']['총거래건수'] == 0
    assert all(df.empty for df in result['individual'].values())
    with pytest.raises(ValueError):
        load_linked_data(path, [], None, (202401,202512), '매매+전세', False)


def test_linked_ui_retains_manual_changes_reload_and_release(tmp_path, monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from projects.chapter09_price_volume.dashboard import db

    path = tmp_path/'ui.duckdb'
    make_db(path)
    monkeypatch.setattr(db, '_DB_PATH', str(path))
    st.cache_data.clear()
    at = AppTest.from_file('projects/chapter09_price_volume/dashboard/app.py',default_timeout=30)
    token = encode_selection(**payload())
    at.query_params['selection'] = token
    at.run()
    assert not at.exception
    assert at.metric[0].value == '4건'
    assert at.slider(key='linked_area').value == (55.,90.)
    at.slider(key='linked_years').set_value((2025,2025)).run()
    assert not at.exception
    assert at.metric[0].value == '2건'
    at.slider(key='linked_area').set_value((83.,85.)).run()
    assert at.metric[0].value == '1건'
    at.run()
    assert at.slider(key='linked_years').value == (2025,2025)
    assert at.slider(key='linked_area').value == (83.,85.)
    assert any('가상A' in w.value for w in at.warning)
    at.multiselect(key='linked_targets').set_value([]).run()
    assert not at.exception and len(at.metric)==0
    at.button(key='linked_release').click().run()
    assert not at.exception
    assert 'selection' not in at.query_params
    assert at.multiselect(key='region_시도').value == ['서울특별시']
    # 새 브라우저 세션은 원래 링크 조건으로 복원된다.
    other = AppTest.from_file('projects/chapter09_price_volume/dashboard/app.py',default_timeout=30)
    other.query_params['selection'] = token
    other.run()
    assert not other.exception and other.metric[0].value == '4건'
    st.cache_data.clear()


def test_invalid_link_ui_does_not_run_default_region(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from projects.chapter09_price_volume.dashboard import db
    path = tmp_path/'ui.duckdb'
    make_db(path)
    monkeypatch.setattr(db, '_DB_PATH', str(path))
    at = AppTest.from_file('projects/chapter09_price_volume/dashboard/app.py',default_timeout=30)
    at.query_params['selection'] = 'invalid!'
    at.run()
    assert not at.exception and len(at.error)==1 and len(at.metric)==0


@pytest.mark.parametrize('schema', ['external','road_only','lease_lot_missing'])
def test_same_identity_as_gap_dashboard_in_reader_and_external_schemas(tmp_path, schema):
    from projects.chapter07_price_gap_table.dashboard.analysis import compare, Query
    path = tmp_path/'identity.duckdb'
    make_db(path)
    con=duckdb.connect(str(path))
    if schema=='external':
        for table, money, amount in [('매매','거래금액','거래금액(만원)'),('전월세','보증금','보증금(만원)')]:
            con.execute(f'ALTER TABLE {table} RENAME COLUMN 전용면적 TO "전용면적(㎡)"')
            con.execute(f'ALTER TABLE {table} RENAME COLUMN {money} TO "{amount}"')
            con.execute(f'ALTER TABLE {table} RENAME COLUMN 지번 TO 번지')
            con.execute(f'ALTER TABLE {table} ADD COLUMN 시도 VARCHAR')
            con.execute(f'ALTER TABLE {table} ADD COLUMN 읍면동 VARCHAR')
            con.execute(f"UPDATE {table} SET 시도=CASE WHEN starts_with(시군구,'서울') THEN '서울특별시' ELSE '경기도' END, 읍면동=CASE WHEN starts_with(시군구,'서울') THEN '역삼동' ELSE '정자동' END")
            con.execute(f"UPDATE {table} SET 시군구=CASE WHEN 시도='서울특별시' THEN '강남구' ELSE '성남시 분당구' END")
    else:
        con.execute('ALTER TABLE 전월세 DROP COLUMN 지번')
        if schema=='road_only':
            con.execute('ALTER TABLE 매매 DROP COLUMN 지번')
    con.close()
    gap=compare(path,Query(202501,202501,bands=('20평대','30평대')))
    targets=[tuple(r[n] for n in ['시도','시군구','읍면동','단지명','주소','평형대']) for r in gap.to_pylist()]
    result=load_linked_data(path,targets,None,(202501,202501),'매매+전세',False)
    assert not result['missing']
    assert result['monthly']['매매']['거래량'].sum()==sum(gap['매매건수'].to_pylist())
    assert result['monthly']['매매']['비교대상'].nunique()==len(targets)
