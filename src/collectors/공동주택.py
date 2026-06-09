"""
공동주택 기본정보 수집 모듈

한국부동산원 API에서 전국 공동주택 단지 기본 정보를 수집하여
DuckDB에 저장한다. 아파트만 필터링하여 저장한다.

이 데이터는 Part07 관심단지 트래킹과 Part09 거래량 지도에서
회전율 계산(거래량 ÷ 세대수)에 사용된다.

사용법:
    python -m src.collectors.공동주택
    python -m src.collectors.공동주택 --sido 서울특별시
"""

import argparse
import sys
from datetime import date
import duckdb
import pandas as pd
from PublicDataReader import Reb
from src.config import DB_PATH, PUBLIC_DATA_API_KEY


# ──────────────────────────────────────────────
# 데이터 수집
# ──────────────────────────────────────────────
def collect_공동주택(api, sido=None):
    """
    공동주택 단지 기본정보를 수집한다.
    한 번의 API 호출로 전국 데이터(약 30만 건)를 가져온다.
    """
    print("  API 호출 중 (전국 데이터)...", end=" ")

    try:
        df = api.get_data(
            service_name="공동주택단지정보",
            category_name="기본",
        )
    except Exception as e:
        print(f"오류: {e}")
        return pd.DataFrame()

    if df is None or len(df) == 0:
        print("데이터 없음")
        return pd.DataFrame()

    print(f"전체 {len(df):,}건")

    # 아파트만 필터링 (단지구분코드 = '1')
    # 1: 아파트, 2: 연립, 3: 다세대 등
    apt_df = df[df["COMPLEX_GB_CD"] == "1"].copy()
    print(f"  아파트 필터링: {len(apt_df):,}건")

    # 시도 필터 (지정된 경우)
    if sido:
        apt_df = apt_df[apt_df["ADRES"].str.startswith(sido)].copy()
        print(f"  시도 필터({sido}): {len(apt_df):,}건")

    # 컬럼 정리
    apt_df = apt_df.rename(columns={
        "COMPLEX_PK": "단지고유번호",
        "PNU": "필지고유번호",
        "ADRES": "주소",
        "COMPLEX_NM1": "단지명",
        "COMPLEX_GB_CD": "단지구분코드",
        "DONG_CNT": "동수",
        "UNIT_CNT": "세대수",
        "USEAPR_DT": "사용승인일",
    })

    # 필요한 컬럼만 선택
    columns = ["단지고유번호", "필지고유번호", "주소", "단지명",
               "단지구분코드", "동수", "세대수", "사용승인일"]
    apt_df = apt_df[columns]

    # 수집일자 추가
    apt_df["수집일자"] = date.today()

    return apt_df


# ──────────────────────────────────────────────
# DuckDB 저장 (전량 교체)
# ──────────────────────────────────────────────
def save_to_duckdb(df):
    """
    DuckDB에 저장한다.
    마스터 데이터이므로 전량 교체한다.
    """
    con = duckdb.connect(DB_PATH)

    con.execute('DROP TABLE IF EXISTS "공동주택_전국"')
    con.execute('CREATE TABLE "공동주택_전국" AS SELECT * FROM df')

    total = con.execute('SELECT COUNT(*) FROM "공동주택_전국"').fetchone()[0]
    con.close()
    return total


# ──────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="공동주택 기본정보 수집")
    parser.add_argument("--sido", type=str, help="특정 시도만 수집 (예: 서울특별시)")
    args = parser.parse_args()

    if not PUBLIC_DATA_API_KEY:
        print("오류: .env 파일에 PUBLIC_DATA_API_KEY를 설정하세요.")
        sys.exit(1)

    api = Reb(PUBLIC_DATA_API_KEY)

    print("=" * 60)
    print("공동주택 단지 정보 수집 (아파트)")
    print("=" * 60)

    df = collect_공동주택(api, args.sido)

    if len(df) > 0:
        total = save_to_duckdb(df)

        print(f"\n{'=' * 60}")
        print("수집 완료")
        print("=" * 60)
        print(f"  공동주택_전국: {total:,}건 (아파트만)")
        print("=" * 60)
    else:
        print("\n수집된 데이터가 없습니다.")


if __name__ == "__main__":
    main()
