"""
피벗테이블 통합 테스트

실제 DuckDB에 연결하여 피벗테이블 생성을 검증한다.
DuckDB 파일이 없으면 자동으로 건너뛴다.
"""
import os

import duckdb
import pytest

from src.config import DB_PATH

DB_EXISTS = os.path.exists(DB_PATH)


def _coordinate_key_ready() -> bool:
    """로컬 DuckDB의 좌표 테이블이 새 도로명주소 키 기준인지 확인한다."""
    if not DB_EXISTS:
        return False

    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        count = con.execute("""
            SELECT COUNT(*)
            FROM 좌표
            WHERE split_part(도로명주소, ' ', 1) IN (
                '서울특별시','부산광역시','대구광역시','인천광역시',
                '광주광역시','대전광역시','울산광역시','세종특별자치시',
                '경기도','강원특별자치도','충청북도','충청남도',
                '전북특별자치도','전라남도','경상북도','경상남도',
                '제주특별자치도'
            )
        """).fetchone()[0]
        return count > 0
    except duckdb.Error:
        return False
    finally:
        con.close()


COORDINATE_KEY_READY = _coordinate_key_ready()


@pytest.mark.skipif(not DB_EXISTS, reason=f"DuckDB 파일이 없습니다: {DB_PATH}")
@pytest.mark.skipif(
    not COORDINATE_KEY_READY,
    reason="좌표 테이블이 시도+시군구+도로명 키 기준으로 아직 재수집되지 않았습니다.",
)
class TestPivotTable:
    """피벗테이블 생성 통합 테스트"""

    def test_서울_강남구_매매(self):
        """서울 강남구 2024년 매매 피벗테이블 기본 검증"""
        from projects.part09_trade_map.dashboard.pivot import generate_pivot_table

        df = generate_pivot_table(
            거래유형="매매",
            시도="서울특별시",
            시군구="강남구",
            연도_시작=2025,
            연도_끝=2025,
        )
        assert len(df) > 0
        assert "거래량" in df.columns
        assert "경도" in df.columns
        assert "위도" in df.columns
        assert "전용면적_구분" in df.columns
        assert df["거래량"].min() >= 1

    def test_서울_회전율(self):
        """서울 지역 회전율 계산 검증"""
        from projects.part09_trade_map.dashboard.pivot import generate_pivot_table

        df = generate_pivot_table(
            거래유형="매매",
            시도="서울특별시",
            시군구="강남구",
            연도_시작=2025,
            연도_끝=2025,
        )
        assert df["세대수"].notna().any(), "서울 강남구에 세대수 매칭이 없습니다"

    def test_전세_조회(self):
        """전세 데이터 조회 테스트"""
        from projects.part09_trade_map.dashboard.pivot import generate_pivot_table

        df = generate_pivot_table(
            거래유형="전세",
            시도="서울특별시",
            시군구="강남구",
            연도_시작=2025,
            연도_끝=2025,
        )
        assert len(df) > 0

    def test_면적대_필터(self):
        """면적대 필터링 테스트"""
        from projects.part09_trade_map.dashboard.pivot import generate_pivot_table

        df = generate_pivot_table(
            거래유형="매매",
            시도="서울특별시",
            시군구="강남구",
            연도_시작=2025,
            연도_끝=2025,
            면적대=["중소형"],
        )
        if len(df) > 0:
            assert (df["전용면적_구분"] == "중소형").all()

    def test_복수_시군구(self):
        """복수 시군구 선택 테스트"""
        from projects.part09_trade_map.dashboard.pivot import generate_pivot_table

        df = generate_pivot_table(
            거래유형="매매",
            시도="서울특별시",
            시군구=["강남구", "서초구"],
            연도_시작=2025,
            연도_끝=2025,
        )
        assert len(df) > 0
        시군구_목록 = df["시군구"].unique()
        assert "강남구" in 시군구_목록 or "서초구" in 시군구_목록


@pytest.mark.skipif(not DB_EXISTS, reason=f"DuckDB 파일이 없습니다: {DB_PATH}")
class TestRegionOptions:
    """지역 옵션 조회 테스트"""

    def test_매매_지역옵션(self):
        from projects.part09_trade_map.dashboard.preprocessing import get_region_options

        regions = get_region_options("매매")
        assert "서울특별시" in regions
        assert "강남구" in regions["서울특별시"]
        assert len(regions["서울특별시"]["강남구"]) > 0

    def test_연도범위(self):
        from projects.part09_trade_map.dashboard.preprocessing import get_year_range

        min_year, max_year = get_year_range("매매")
        assert min_year > 2000
        assert max_year >= 2025
        assert min_year < max_year
