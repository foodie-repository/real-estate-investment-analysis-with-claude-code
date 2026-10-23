import json

import duckdb
import pytest

from projects.chapter05_roi import targets as targets_module
from projects.chapter05_roi import calculator as calculator_module
from projects.chapter05_roi.calculator import (
    _get_price_at,
    _get_단지정보,
    calculate_roi,
)


def test_get_price_at_keeps_active_trade_marked_with_hyphen():
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE 매매 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전용면적 DOUBLE,
            계약년월 BIGINT,
            계약일 BIGINT,
            거래금액 BIGINT,
            층 BIGINT,
            해제사유발생일 VARCHAR,
            거래유형 VARCHAR
        )
        """
    )
    con.executemany(
        "INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("서울특별시 테스트구 테스트동", "테스트단지", 84.0, 202001, 20, 100_000, 10, "-", "-"),
            ("서울특별시 테스트구 테스트동", "테스트단지", 84.0, 202001, 25, 200_000, 15, "20200201", "-"),
        ],
    )

    try:
        assert _get_price_at(con, "테스트단지", 84.0, 202001, "매매") == 100_000
    finally:
        con.close()


def test_get_price_at_filters_same_name_apartment_by_region():
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE 매매 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전용면적 DOUBLE,
            계약년월 BIGINT,
            계약일 BIGINT,
            거래금액 BIGINT,
            층 BIGINT,
            해제사유발생일 VARCHAR,
            거래유형 VARCHAR
        )
        """
    )
    con.executemany(
        "INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("서울특별시 테스트구 테스트동", "같은이름단지", 84.0, 202001, 20, 100_000, 10, "None", "중개거래"),
            ("부산광역시 테스트구 테스트동", "같은이름단지", 84.0, 202001, 25, 200_000, 20, "None", "중개거래"),
        ],
    )

    try:
        assert _get_price_at(
            con,
            "같은이름단지",
            84.0,
            202001,
            "매매",
            시군구_full="서울특별시 테스트구 테스트동",
        ) == 100_000
    finally:
        con.close()


def test_get_price_at_uses_latest_valid_contract_in_target_month():
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE 매매 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전용면적 DOUBLE,
            계약년월 BIGINT,
            계약일 BIGINT,
            거래금액 BIGINT,
            층 BIGINT,
            해제사유발생일 VARCHAR,
            거래유형 VARCHAR
        )
        """
    )
    con.executemany(
        "INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("서울특별시 테스트구 테스트동", "테스트단지", 84.0, 202001, 5, 100_000, 5, "None", "중개거래"),
            ("서울특별시 테스트구 테스트동", "테스트단지", 84.0, 202001, 15, 150_000, 10, "None", "중개거래"),
            ("서울특별시 테스트구 테스트동", "테스트단지", 84.0, 202001, 20, 200_000, 20, "None", "직거래"),
            ("서울특별시 테스트구 테스트동", "테스트단지", 84.0, 202001, 25, 250_000, 25, "20200201", "중개거래"),
        ],
    )

    try:
        assert _get_price_at(con, "테스트단지", 84.0, 202001, "매매") == 150_000
    finally:
        con.close()


def test_get_price_at_uses_nearest_month_and_enforces_twelve_month_limit():
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE 매매 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전용면적 DOUBLE,
            계약년월 BIGINT,
            계약일 BIGINT,
            거래금액 BIGINT,
            층 BIGINT,
            해제사유발생일 VARCHAR,
            거래유형 VARCHAR
        )
        """
    )
    con.executemany(
        "INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("서울특별시 테스트구 테스트동", "근접단지", 84.0, 201912, 30, 90_000, 10, "None", "중개거래"),
            ("서울특별시 테스트구 테스트동", "근접단지", 84.0, 202002, 1, 110_000, 10, "None", "중개거래"),
            ("서울특별시 테스트구 테스트동", "12개월단지", 84.0, 201901, 10, 120_000, 10, "None", "중개거래"),
            ("서울특별시 테스트구 테스트동", "13개월단지", 84.0, 201812, 10, 130_000, 10, "None", "중개거래"),
        ],
    )

    try:
        assert _get_price_at(con, "근접단지", 84.0, 202001, "매매") == 110_000
        assert _get_price_at(con, "12개월단지", 84.0, 202001, "매매") == 120_000
        assert _get_price_at(con, "13개월단지", 84.0, 202001, "매매") is None
    finally:
        con.close()


def test_get_complex_info_filters_build_year_by_region():
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE 공동주택_전국 (
            주소 VARCHAR,
            단지명 VARCHAR,
            세대수 BIGINT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE 매매 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전용면적 DOUBLE,
            건축년도 BIGINT
        )
        """
    )
    con.executemany(
        "INSERT INTO 공동주택_전국 VALUES (?, ?, ?)",
        [
            ("서울특별시 테스트구 테스트동 1", "같은이름단지", 1_000),
            ("부산광역시 테스트구 테스트동 2", "같은이름단지", 500),
        ],
    )
    con.executemany(
        "INSERT INTO 매매 VALUES (?, ?, ?, ?)",
        [
            ("부산광역시 테스트구 테스트동", "같은이름단지", 84.0, 1990),
            ("서울특별시 테스트구 테스트동", "같은이름단지", 84.0, 2020),
        ],
    )

    try:
        result = _get_단지정보(
            con,
            "같은이름단지",
            "서울특별시 테스트구 테스트동",
            84.0,
        )
        assert result["건축년도"] == 2020
    finally:
        con.close()


def test_add_uses_closest_actual_area_within_allowed_range(tmp_path, monkeypatch):
    db_path = tmp_path / "targets.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE 매매 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전용면적 DOUBLE
        )
        """
    )
    con.executemany(
        "INSERT INTO 매매 VALUES (?, ?, ?)",
        [
            ("서울특별시 테스트구 테스트동", "테스트단지", 84.74),
            ("서울특별시 테스트구 테스트동", "테스트단지", 84.94),
        ],
    )
    con.close()

    monkeypatch.setattr(targets_module, "DB_PATH", db_path)
    monkeypatch.setattr(targets_module, "TARGETS_PATH", tmp_path / "targets.json")

    targets_module.add("테스트단지", 84.74)

    assert targets_module.get_all() == [
        {
            "시군구": "서울특별시 테스트구 테스트동",
            "단지명": "테스트단지",
            "전용면적": 84.74,
        }
    ]


def test_add_accepts_region_to_disambiguate_same_name_complex(tmp_path, monkeypatch):
    db_path = tmp_path / "same_name.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE 매매 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전용면적 DOUBLE
        )
        """
    )
    con.executemany(
        "INSERT INTO 매매 VALUES (?, ?, ?)",
        [
            ("서울특별시 테스트구 테스트동", "같은이름단지", 84.0),
            ("부산광역시 테스트구 테스트동", "같은이름단지", 84.0),
        ],
    )
    con.close()

    monkeypatch.setattr(targets_module, "DB_PATH", db_path)
    monkeypatch.setattr(targets_module, "TARGETS_PATH", tmp_path / "targets.json")

    targets_module.add(
        "같은이름단지",
        84.0,
        시군구="서울특별시 테스트구 테스트동",
    )

    assert targets_module.get_all() == [
        {
            "시군구": "서울특별시 테스트구 테스트동",
            "단지명": "같은이름단지",
            "전용면적": 84.0,
        }
    ]


@pytest.mark.parametrize("reverse_rows", [False, True])
def test_target_month_sale_selection_is_deterministic(reverse_rows):
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE 매매 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전용면적 DOUBLE,
            계약년월 BIGINT,
            계약일 BIGINT,
            거래금액 BIGINT,
            층 BIGINT,
            해제사유발생일 VARCHAR,
            거래유형 VARCHAR
        )
        """
    )
    rows = [
        ("서울특별시 테스트구 테스트동", "결정단지", 84.80, 202201, 25, 200_000, 20, "None", "중개거래"),
        ("서울특별시 테스트구 테스트동", "결정단지", 84.94, 202201, 25, 150_000, 10, "None", "중개거래"),
        ("서울특별시 테스트구 테스트동", "결정단지", 84.94, 202201, 25, 160_000, 5, "None", "중개거래"),
    ]
    if reverse_rows:
        rows.reverse()
    con.executemany("INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

    try:
        assert _get_price_at(con, "결정단지", 84.94, 202201, "매매") == 160_000
    finally:
        con.close()


@pytest.mark.parametrize("reverse_rows", [False, True])
def test_target_month_rent_selection_is_deterministic_and_excludes_monthly_rent(
    reverse_rows,
):
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE 전월세 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전월세구분 VARCHAR,
            전용면적 DOUBLE,
            계약년월 BIGINT,
            계약일 BIGINT,
            보증금 BIGINT,
            월세금 BIGINT,
            층 BIGINT
        )
        """
    )
    rows = [
        ("서울특별시 테스트구 테스트동", "결정단지", "전세", 84.80, 202201, 25, 120_000, 0, 20),
        ("서울특별시 테스트구 테스트동", "결정단지", "전세", 84.94, 202201, 25, 100_000, 0, 10),
        ("서울특별시 테스트구 테스트동", "결정단지", "전세", 84.94, 202201, 25, 110_000, 0, 5),
        ("서울특별시 테스트구 테스트동", "결정단지", "월세", 84.94, 202201, 31, 500_000, 100, 30),
    ]
    if reverse_rows:
        rows.reverse()
    con.executemany("INSERT INTO 전월세 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

    try:
        assert _get_price_at(con, "결정단지", 84.94, 202201, "전월세") == 110_000
    finally:
        con.close()


@pytest.mark.parametrize("reverse_rows", [False, True])
def test_nearest_sale_tie_uses_later_calendar_month_before_trade_details(
    reverse_rows,
):
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE 매매 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전용면적 DOUBLE,
            계약년월 BIGINT,
            계약일 BIGINT,
            거래금액 BIGINT,
            층 BIGINT,
            해제사유발생일 VARCHAR,
            거래유형 VARCHAR
        )
        """
    )
    rows = [
        ("서울특별시 테스트구 테스트동", "동률단지", 84.94, 202112, 27, 251_000, 20, "None", "중개거래"),
        ("서울특별시 테스트구 테스트동", "동률단지", 84.80, 202202, 18, 260_000, 25, "None", "중개거래"),
        ("서울특별시 테스트구 테스트동", "동률단지", 84.94, 202202, 18, 250_000, 10, "None", "중개거래"),
        ("서울특별시 테스트구 테스트동", "동률단지", 84.94, 202202, 18, 255_000, 5, "None", "중개거래"),
    ]
    if reverse_rows:
        rows.reverse()
    con.executemany("INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

    try:
        assert _get_price_at(con, "동률단지", 84.94, 202201, "매매") == 255_000
    finally:
        con.close()


@pytest.mark.parametrize("reverse_rows", [False, True])
def test_nearest_rent_tie_uses_later_calendar_month_before_trade_details(
    reverse_rows,
):
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE 전월세 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전월세구분 VARCHAR,
            전용면적 DOUBLE,
            계약년월 BIGINT,
            계약일 BIGINT,
            보증금 BIGINT,
            월세금 BIGINT,
            층 BIGINT
        )
        """
    )
    rows = [
        ("서울특별시 테스트구 테스트동", "동률단지", "전세", 84.94, 202112, 27, 100_000, 0, 20),
        ("서울특별시 테스트구 테스트동", "동률단지", "전세", 84.80, 202202, 18, 120_000, 0, 25),
        ("서울특별시 테스트구 테스트동", "동률단지", "전세", 84.94, 202202, 18, 90_000, 0, 10),
        ("서울특별시 테스트구 테스트동", "동률단지", "전세", 84.94, 202202, 18, 95_000, 0, 5),
    ]
    if reverse_rows:
        rows.reverse()
    con.executemany("INSERT INTO 전월세 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

    try:
        assert _get_price_at(con, "동률단지", 84.94, 202201, "전월세") == 95_000
    finally:
        con.close()


def _target_rows():
    return [
        {
            "시군구": "서울특별시 테스트구 테스트동",
            "단지명": "같은이름단지",
            "전용면적": 84.0,
        },
        {
            "시군구": "부산광역시 테스트구 테스트동",
            "단지명": "같은이름단지",
            "전용면적": 84.0,
        },
    ]


def test_remove_keeps_same_name_targets_when_region_is_ambiguous(
    tmp_path,
    monkeypatch,
    capsys,
):
    targets_path = tmp_path / "targets.json"
    targets_path.write_text(
        json.dumps(_target_rows(), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(targets_module, "TARGETS_PATH", targets_path)

    targets_module.remove("같은이름단지", 84.0)

    assert targets_module.get_all() == _target_rows()
    assert "여러 지역" in capsys.readouterr().out


def test_remove_with_region_deletes_only_matching_target(tmp_path, monkeypatch):
    targets_path = tmp_path / "targets.json"
    rows = [
        *_target_rows(),
        {
            "시군구": "서울특별시 테스트구 테스트동",
            "단지명": "같은이름단지",
            "전용면적": 84.5,
        },
    ]
    targets_path.write_text(
        json.dumps(rows, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(targets_module, "TARGETS_PATH", targets_path)

    targets_module.remove(
        "같은이름단지",
        84.0,
        시군구="서울특별시 테스트구 테스트동",
    )

    assert targets_module.get_all() == [rows[1], rows[2]]


def _create_roi_db(db_path, purchase_rent):
    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE 공동주택_전국 (
            주소 VARCHAR,
            단지명 VARCHAR,
            세대수 BIGINT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE 매매 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전용면적 DOUBLE,
            계약년월 BIGINT,
            계약일 BIGINT,
            거래금액 BIGINT,
            층 BIGINT,
            건축년도 BIGINT,
            해제사유발생일 VARCHAR,
            거래유형 VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE 전월세 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전월세구분 VARCHAR,
            전용면적 DOUBLE,
            계약년월 BIGINT,
            계약일 BIGINT,
            보증금 BIGINT,
            월세금 BIGINT,
            층 BIGINT
        )
        """
    )
    con.execute(
        "INSERT INTO 공동주택_전국 VALUES (?, ?, ?)",
        ["서울특별시 테스트구 테스트동 1", "수익률단지", 1_000],
    )
    con.executemany(
        "INSERT INTO 매매 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("서울특별시 테스트구 테스트동", "수익률단지", 84.0, 202001, 20, 100_000, 10, 2010, "None", "중개거래"),
            ("서울특별시 테스트구 테스트동", "수익률단지", 84.0, 202201, 20, 130_000, 10, 2010, "None", "중개거래"),
        ],
    )
    con.executemany(
        "INSERT INTO 전월세 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("서울특별시 테스트구 테스트동", "수익률단지", "전세", 84.0, 202001, 20, purchase_rent, 0, 10),
            ("서울특별시 테스트구 테스트동", "수익률단지", "월세", 84.0, 202001, 31, 500_000, 100, 20),
            ("서울특별시 테스트구 테스트동", "수익률단지", "전세", 84.0, 202201, 20, 70_000, 0, 10),
        ],
    )
    con.close()


def _calculate_test_roi(tmp_path, monkeypatch, purchase_rent):
    db_path = tmp_path / f"roi_{purchase_rent}.duckdb"
    _create_roi_db(db_path, purchase_rent)
    monkeypatch.setattr(calculator_module, "DB_PATH", db_path)
    return calculate_roi(
        [
            {
                "시군구": "서울특별시 테스트구 테스트동",
                "단지명": "수익률단지",
                "전용면적": 84.0,
            }
        ],
        202001,
        [2],
    )[0]


def test_calculate_roi_computes_gap_profit_and_return(tmp_path, monkeypatch):
    result = _calculate_test_roi(tmp_path, monkeypatch, purchase_rent=60_000)

    assert result["매수_갭"] == 40_000
    assert result["2년_갭"] == 60_000
    assert result["2년_매매차익"] == 30_000
    assert result["2년_수익률"] == 75.0


@pytest.mark.parametrize(
    ("purchase_rent", "expected_gap"),
    [
        (100_000, 0),
        (110_000, -10_000),
    ],
)
def test_calculate_roi_omits_return_for_zero_or_negative_gap(
    tmp_path,
    monkeypatch,
    purchase_rent,
    expected_gap,
):
    result = _calculate_test_roi(tmp_path, monkeypatch, purchase_rent)

    assert result["매수_갭"] == expected_gap
    assert result["2년_매매차익"] == 30_000
    assert result["2년_수익률"] is None
