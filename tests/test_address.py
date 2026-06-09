import unittest

from src.utils.address import get_sigungu_lookup_keyword, parse_sigungu


class AddressUtilsTest(unittest.TestCase):
    def test_parse_sigungu_for_seoul(self):
        parsed = parse_sigungu("서울특별시 강동구 고덕동")
        self.assertEqual(
            parsed,
            {"시도": "서울특별시", "시군구": "강동구", "읍면동": "고덕동"},
        )

    def test_parse_sigungu_for_two_level_district(self):
        parsed = parse_sigungu("경기도 성남시 분당구 정자동")
        self.assertEqual(
            parsed,
            {"시도": "경기도", "시군구": "성남시 분당구", "읍면동": "정자동"},
        )

    def test_parse_sigungu_for_sejong(self):
        parsed = parse_sigungu("세종특별자치시 한솔동")
        self.assertEqual(
            parsed,
            {"시도": "세종특별자치시", "시군구": "세종시", "읍면동": "한솔동"},
        )

    def test_lookup_keyword_for_two_level_district(self):
        keyword = get_sigungu_lookup_keyword("경기도 성남시 분당구 정자동")
        self.assertEqual(keyword, "성남시 분당구")


if __name__ == "__main__":
    unittest.main()
