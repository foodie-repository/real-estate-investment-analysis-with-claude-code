import duckdb

from projects.chapter04_tracking import tracker
from projects.chapter04_tracking.tracker import _build_tracking_row


def _create_tracking_db():
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE 매매 (
            시군구 VARCHAR,
            단지명 VARCHAR,
            전용면적 DOUBLE,
            계약년월 BIGINT,
            계약일 BIGINT,
            거래금액 BIGINT,
            층 BIGINT,
            건축년도 BIGINT,
            도로명 VARCHAR,
            매수자 VARCHAR,
            매도자 VARCHAR,
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
            계약년월 BIGINT,
            계약일 BIGINT,
            보증금 BIGINT,
            월세금 BIGINT,
            층 BIGINT,
            건축년도 BIGINT,
            도로명 VARCHAR,
            계약기간 VARCHAR,
            계약구분 VARCHAR,
            갱신요구권사용 VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE 공동주택_전국 (
            단지명 VARCHAR,
            주소 VARCHAR,
            세대수 BIGINT
        )
    """)
    con.execute("""
        INSERT INTO 공동주택_전국 VALUES
        ('테스트단지', '서울특별시 강동구 테스트로 1', 1000)
    """)
    return con


def _insert_sale(
    con,
    계약년월,
    거래금액,
    *,
    계약일=15,
    전용면적=84.24,
    거래유형="중개거래",
    해제사유발생일=None,
):
    con.execute(
        """
        INSERT INTO 매매 VALUES (
            '서울특별시 강동구 테스트동', '테스트단지', ?, ?, ?, ?, 10, 2020,
            '테스트로', NULL, NULL, ?, ?
        )
        """,
        [전용면적, 계약년월, 계약일, 거래금액, 해제사유발생일, 거래유형],
    )


def _insert_jeonse(
    con,
    계약년월,
    보증금,
    *,
    계약일=15,
    전용면적=84.24,
    계약구분="신규",
    갱신요구권사용="",
):
    con.execute(
        """
        INSERT INTO 전월세 VALUES (
            '서울특별시 강동구 테스트동', '테스트단지', '전세', ?, ?, ?, ?, 0,
            10, 2020, '테스트로', '2년', ?, ?
        )
        """,
        [전용면적, 계약년월, 계약일, 보증금, 계약구분, 갱신요구권사용],
    )


def test_tracking_uses_latest_month_shared_by_sale_and_new_jeonse():
    """매매·신규 전세의 최신월이 달라도 서로 다른 월의 금액을 결합하지 않는다."""
    con = _create_tracking_db()
    try:
        _insert_sale(con, 202501, 100_000)
        _insert_sale(con, 202502, 120_000)
        _insert_sale(con, 202503, 140_000)
        _insert_jeonse(con, 202501, 60_000)
        _insert_jeonse(con, 202502, 70_000)
        _insert_jeonse(con, 202504, 90_000)

        result = _build_tracking_row(
            con,
            "테스트단지",
            "서울특별시 강동구 테스트동",
            84.24,
        )
    finally:
        con.close()

    assert result["기준월"] == 202502
    assert result["최근매매가"] == 120_000
    assert result["최근전세가"] == 70_000
    assert result["매매전세갭"] == 50_000
    assert result["전세가율"] == 58.3


def test_tracking_uses_medians_and_separates_trade_characteristics():
    """월별 중앙값을 사용하고 직거래·취소 거래와 신규·갱신 전세를 구분한다."""
    con = _create_tracking_db()
    try:
        _insert_sale(con, 202503, 100_000, 계약일=1)
        _insert_sale(con, 202503, 120_000, 계약일=10)
        _insert_sale(con, 202503, 300_000, 계약일=20)
        _insert_sale(con, 202503, 50_000, 계약일=25, 거래유형="직거래")
        _insert_sale(
            con,
            202503,
            500_000,
            계약일=28,
            해제사유발생일="2025-04-01",
        )
        _insert_jeonse(con, 202503, 60_000, 계약일=1)
        _insert_jeonse(con, 202503, 80_000, 계약일=10)
        _insert_jeonse(con, 202503, 50_000, 계약일=15, 계약구분="갱신")
        _insert_jeonse(con, 202503, 55_000, 계약일=20, 계약구분="갱신")
        _insert_jeonse(con, 202503, 90_000, 계약일=25, 계약구분="갱신")

        result = _build_tracking_row(
            con,
            "테스트단지",
            "서울특별시 강동구 테스트동",
            84.24,
        )
    finally:
        con.close()

    assert result["최근매매가"] == 120_000
    assert result["매매거래건수"] == 3
    assert result["직거래제외건수"] == 1
    assert result["최근전세가"] == 70_000
    assert result["신규전세거래건수"] == 2
    assert result["갱신전세가"] == 55_000
    assert result["갱신전세거래건수"] == 3
    assert result["매매전세갭"] == 50_000
    assert result["전세가율"] == 58.3


def test_tracking_keeps_selected_area_separate_from_nearby_area_types():
    """선택한 전용면적의 시세에 같은 평형대의 다른 면적을 섞지 않는다."""
    con = _create_tracking_db()
    try:
        _insert_sale(con, 202503, 100_000, 전용면적=84.24)
        _insert_jeonse(con, 202503, 60_000, 전용면적=84.24)
        _insert_sale(con, 202503, 300_000, 전용면적=84.3)
        _insert_jeonse(con, 202503, 90_000, 전용면적=84.3)

        result = _build_tracking_row(
            con,
            "테스트단지",
            "서울특별시 강동구 테스트동",
            84.24,
        )
    finally:
        con.close()

    assert result["최근매매가"] == 100_000
    assert result["매매거래건수"] == 1
    assert result["최근전세가"] == 60_000
    assert result["신규전세거래건수"] == 1


def test_previous_values_use_the_calendar_previous_month_without_fallback():
    """전월 거래가 없으면 더 오래된 달을 전월 값으로 대신 사용하지 않는다."""
    con = _create_tracking_db()
    try:
        _insert_sale(con, 202501, 90_000)
        _insert_jeonse(con, 202501, 50_000)
        _insert_sale(con, 202503, 120_000)
        _insert_jeonse(con, 202503, 70_000)

        result = _build_tracking_row(
            con,
            "테스트단지",
            "서울특별시 강동구 테스트동",
            84.24,
        )
    finally:
        con.close()

    assert result["기준월"] == 202503
    assert result["전월기준월"] == 202502
    assert result["전월매매"] is None
    assert result["전월전세"] is None
    assert result["매매전월대비"] is None
    assert result["전세전월대비"] is None


def test_recent_reference_month_is_marked_as_provisional(monkeypatch):
    """실행 시점의 현재월·전월 기준월은 신고가 추가될 수 있다고 표시한다."""
    con = _create_tracking_db()
    try:
        monkeypatch.setattr(
            tracker,
            "_current_year_month",
            lambda: 202504,
            raising=False,
        )
        _insert_sale(con, 202503, 120_000)
        _insert_jeonse(con, 202503, 70_000)
        _insert_sale(con, 202504, 130_000)

        result = _build_tracking_row(
            con,
            "테스트단지",
            "서울특별시 강동구 테스트동",
            84.24,
        )
    finally:
        con.close()

    assert result["기준월"] == 202503
    assert result["데이터최신월"] == 202504
    assert result["잠정수치"] is True
    assert result["비고"] == "최근 1~2개월 잠정 수치"


def test_stale_data_tail_is_reported_as_needing_refresh(monkeypatch):
    """오래된 DB의 마지막 달을 잠정 수치로 오인하지 않고 갱신 필요를 알린다."""
    con = _create_tracking_db()
    try:
        monkeypatch.setattr(
            tracker,
            "_current_year_month",
            lambda: 202608,
            raising=False,
        )
        _insert_sale(con, 202503, 120_000)
        _insert_jeonse(con, 202503, 70_000)
        _insert_sale(con, 202504, 130_000)

        result = _build_tracking_row(
            con,
            "테스트단지",
            "서울특별시 강동구 테스트동",
            84.24,
        )
    finally:
        con.close()

    assert result["기준월"] == 202503
    assert result["데이터최신월"] == 202504
    assert result["잠정수치"] is False
    assert result["비고"] == "데이터 최신월 202504: 갱신 필요"


def test_missing_common_month_is_reported_instead_of_combining_other_months():
    """동일 기준월이 없으면 빈 결과의 이유를 알려준다."""
    con = _create_tracking_db()
    try:
        _insert_sale(con, 202503, 120_000)
        _insert_jeonse(con, 202504, 70_000)

        result = _build_tracking_row(
            con,
            "테스트단지",
            "서울특별시 강동구 테스트동",
            84.24,
        )
    finally:
        con.close()

    assert result["기준월"] is None
    assert result["최근매매가"] is None
    assert result["최근전세가"] is None
    assert result["전세가율"] is None
    assert result["비고"] == "동일 기준월의 중개 매매·신규 전세 없음"


def test_peak_price_uses_active_brokered_sales_only():
    """전고점 비교 기준에 직거래나 취소 거래를 포함하지 않는다."""
    con = _create_tracking_db()
    try:
        _insert_sale(con, 202401, 300_000, 거래유형="중개거래")
        _insert_sale(con, 202402, 500_000, 거래유형="직거래")
        _insert_sale(
            con,
            202403,
            600_000,
            거래유형="중개거래",
            해제사유발생일="2024-04-01",
        )
        _insert_sale(con, 202503, 120_000, 거래유형="중개거래")
        _insert_jeonse(con, 202503, 70_000)

        result = _build_tracking_row(
            con,
            "테스트단지",
            "서울특별시 강동구 테스트동",
            84.24,
        )
    finally:
        con.close()

    assert result["전고점"] == 300_000
    assert result["전고점대비"] == -60.0
