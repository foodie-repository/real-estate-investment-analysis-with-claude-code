import unittest

import duckdb

from src.preprocessing.trade import build_query, preprocess
from src.utils.address import parse_sigungu


class PreprocessingQueryTest(unittest.TestCase):
    def test_build_query_with_default_steps(self):
        query = build_query("매매")
        self.assertIn('FROM "매매"', query)
        self.assertIn("주소파싱 AS", query)
        self.assertIn("연식계산 AS", query)

    def test_build_query_with_empty_steps(self):
        query = build_query("전월세", steps=[])
        self.assertEqual(query, 'SELECT * FROM "전월세"')

    def test_build_query_raises_for_unknown_step(self):
        with self.assertRaises(ValueError):
            build_query("매매", steps=["없는단계"])

    def test_address_parsing_step_matches_common_parser(self):
        cases = [
            "경기도 성남시 분당구 정자동",
            "충청남도 예산군 예산읍 예산리",
            "세종특별자치시  조치원읍 상리",
        ]

        con = duckdb.connect(":memory:")
        try:
            con.execute('CREATE TABLE "매매" (시군구 VARCHAR)')
            con.executemany('INSERT INTO "매매" VALUES (?)', [(case,) for case in cases])

            df = preprocess("매매", steps=["주소파싱"], con=con).df()
        finally:
            con.close()

        for _, row in df.iterrows():
            expected = parse_sigungu(row["시군구"])
            self.assertEqual(row["시도"], expected["시도"])
            self.assertEqual(row["시군구2"], expected["시군구"])
            self.assertEqual(row["읍면동"], expected["읍면동"])


if __name__ == "__main__":
    unittest.main()
