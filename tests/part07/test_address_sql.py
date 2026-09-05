"""
주소 파싱 및 도로명주소 키 생성 테스트

Python 함수와 SQL 표현식이 동일한 결과를 내는지 검증한다.
"""
import duckdb

from src.utils.address import (
    parse_sigungu,
    build_road_address_key,
    SIDO_SQL,
    SIGUNGU_SQL,
    EUPMYEONDONG_SQL,
)


def _parse_sigungu_with_sql(value: str) -> dict[str, str]:
    con = duckdb.connect(":memory:")
    try:
        row = con.execute(
            f"""
            SELECT
                {SIDO_SQL} AS 시도,
                {SIGUNGU_SQL} AS 시군구,
                {EUPMYEONDONG_SQL} AS 읍면동
            FROM (SELECT ? AS 시군구)
            """,
            [value],
        ).fetchone()
    finally:
        con.close()

    return {"시도": row[0], "시군구": row[1], "읍면동": row[2]}


# =============================================================================
# parse_sigungu 테스트
# =============================================================================
class TestParseSigungu:
    """시군구 파싱 테스트"""

    def test_서울_3part(self):
        result = parse_sigungu("서울특별시 강남구 압구정동")
        assert result["시도"] == "서울특별시"
        assert result["시군구"] == "강남구"
        assert result["읍면동"] == "압구정동"

    def test_광역시_3part(self):
        result = parse_sigungu("부산광역시 해운대구 우동")
        assert result["시도"] == "부산광역시"
        assert result["시군구"] == "해운대구"
        assert result["읍면동"] == "우동"

    def test_도_시_구_4part(self):
        """4-part(구): 경기도 성남시 중원구 은행동"""
        result = parse_sigungu("경기도 성남시 중원구 은행동")
        assert result["시도"] == "경기도"
        assert result["시군구"] == "성남시 중원구"
        assert result["읍면동"] == "은행동"

    def test_도_군_읍_리_4part(self):
        """4-part(읍리): 충청남도 예산군 예산읍 예산리"""
        result = parse_sigungu("충청남도 예산군 예산읍 예산리")
        assert result["시도"] == "충청남도"
        assert result["시군구"] == "예산군 예산읍"
        assert result["읍면동"] == "예산리"

    def test_세종(self):
        result = parse_sigungu("세종특별자치시 한솔동")
        assert result["시도"] == "세종특별자치시"
        assert result["시군구"] == "세종시"
        assert result["읍면동"] == "한솔동"

    def test_세종_double_space(self):
        """더블스페이스: 세종특별자치시  조치원읍 상리"""
        result = parse_sigungu("세종특별자치시  조치원읍 상리")
        assert result["시도"] == "세종특별자치시"
        assert result["시군구"] == "세종시"
        assert result["읍면동"] == "조치원읍"

    def test_2part_no_dong(self):
        result = parse_sigungu("부산광역시 서구")
        assert result["시도"] == "부산광역시"
        assert result["시군구"] == "서구"
        assert result["읍면동"] == ""


class TestSqlMatchesPythonParseSigungu:
    """Python 주소 파싱과 DuckDB SQL 주소 파싱의 결과가 같아야 한다."""

    def test_sql_matches_python_for_common_address_patterns(self):
        cases = [
            "서울특별시 강남구 압구정동",
            "부산광역시 해운대구 우동",
            "경기도 성남시 중원구 은행동",
            "충청남도 예산군 예산읍 예산리",
            "충청남도 천안시 서북구 성환읍 율금리",
            "세종특별자치시 한솔동",
            "세종특별자치시  조치원읍 상리",
            "부산광역시 서구",
        ]

        for case in cases:
            assert _parse_sigungu_with_sql(case) == parse_sigungu(case)


# =============================================================================
# build_road_address_key 테스트
# =============================================================================
class TestBuildRoadAddressKey:
    """도로명주소 키 생성 테스트"""

    def test_서울(self):
        key = build_road_address_key("서울특별시 강남구 압구정동", "압구정로 201")
        assert key == "서울특별시 강남구 압구정로 201"

    def test_광역시(self):
        key = build_road_address_key("부산광역시 해운대구 우동", "해운대해변로 52")
        assert key == "부산광역시 해운대구 해운대해변로 52"

    def test_도_시_구(self):
        """도+시+구: 도 + 시 + 도로명 (구 제거)"""
        key = build_road_address_key("경기도 성남시 중원구 은행동", "수내로192번길 25")
        assert key == "경기도 성남시 수내로192번길 25"

    def test_도_군(self):
        key = build_road_address_key("충청남도 예산군 예산읍 예산리", "아리랑로144번길 19")
        assert key == "충청남도 예산군 아리랑로144번길 19"

    def test_세종(self):
        key = build_road_address_key("세종특별자치시  조치원읍 상리", "세종로 1")
        assert key == "세종특별자치시 세종시 세종로 1"

    def test_empty_input(self):
        assert build_road_address_key("", "압구정로 201") == ""
        assert build_road_address_key("서울특별시 강남구 압구정동", "") == ""
