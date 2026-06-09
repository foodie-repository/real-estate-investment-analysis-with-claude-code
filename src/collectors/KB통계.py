"""
KB부동산 통계 수집 모듈

PublicDataReader의 Kbland 모듈을 사용하여 KB부동산 통계 데이터를 수집한다.
API 키 없이 사용 가능하다.

수집 지표:
    - KB_매매가격지수: 지역별 매매가격 추이 (2019.01=100)
    - KB_전세가격지수: 지역별 전세가격 추이
    - KB_전세가율: 매매 대비 전세 비율

사용법:
    python -m src.collectors.KB통계
    python -m src.collectors.KB통계 --indicator 매매가격지수
"""

import argparse
import sys
import time
import duckdb
import pandas as pd
from PublicDataReader import Kbland
from src.config import DB_PATH


# ──────────────────────────────────────────────
# 지표별 수집 함수
# ──────────────────────────────────────────────
def collect_매매가격지수(api):
    """
    KB 매매가격지수를 수집한다.
    월간, 아파트 기준으로 전국 데이터를 가져온다.
    """
    try:
        df = api.get_price_index(
            월간주간구분코드="01",  # 월간
            매물종별구분="01",      # 아파트
            매매전세코드="01",      # 매매
        )
        if df is not None and len(df) > 0:
            return df
    except Exception as e:
        print(f"  오류: {e}")

    return pd.DataFrame()


def collect_전세가격지수(api):
    """
    KB 전세가격지수를 수집한다.
    월간, 아파트 기준으로 전국 데이터를 가져온다.
    """
    try:
        df = api.get_price_index(
            월간주간구분코드="01",  # 월간
            매물종별구분="01",      # 아파트
            매매전세코드="02",      # 전세
        )
        if df is not None and len(df) > 0:
            return df
    except Exception as e:
        print(f"  오류: {e}")

    return pd.DataFrame()


def collect_전세가율(api):
    """
    KB 전세가율을 수집한다.
    아파트 기준으로 전국 데이터를 가져온다.
    """
    try:
        df = api.get_jeonse_price_ratio(
            매물종별구분="01",  # 아파트
        )
        if df is not None and len(df) > 0:
            return df
    except Exception as e:
        print(f"  오류: {e}")

    return pd.DataFrame()


# ──────────────────────────────────────────────
# DuckDB 저장 (전량 교체)
# ──────────────────────────────────────────────
def save_to_duckdb(df, table_name):
    """
    DuckDB에 저장한다.
    기존 테이블이 있으면 삭제 후 재저장 (전량 교체).
    """
    con = duckdb.connect(DB_PATH)

    # 기존 테이블 삭제
    con.execute(f'DROP TABLE IF EXISTS "{table_name}"')

    # 새로 생성
    con.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM df')

    total = con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
    con.close()
    return total


# ──────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────
# 지표 이름 → (수집 함수, 테이블 이름) 매핑
INDICATORS = {
    "매매가격지수": (collect_매매가격지수, "KB_매매가격지수"),
    "전세가격지수": (collect_전세가격지수, "KB_전세가격지수"),
    "전세가율": (collect_전세가율, "KB_전세가율"),
}


def main():
    parser = argparse.ArgumentParser(description="KB부동산 통계 수집")
    parser.add_argument(
        "--indicator",
        type=str,
        choices=list(INDICATORS.keys()),
        help="특정 지표만 수집",
    )
    args = parser.parse_args()

    # 수집 대상 결정
    if args.indicator:
        targets = {args.indicator: INDICATORS[args.indicator]}
    else:
        targets = INDICATORS

    api = Kbland()

    print("=" * 60)
    print("KB부동산 통계 수집")
    print("=" * 60)
    print(f"수집 지표: {', '.join(targets.keys())}")
    print("=" * 60)

    results = {}

    for i, (name, (collect_fn, table_name)) in enumerate(targets.items(), 1):
        print(f"\n[{i}/{len(targets)}] {name} 수집 중...")

        df = collect_fn(api)

        if len(df) > 0:
            total = save_to_duckdb(df, table_name)
            results[table_name] = total
            print(f"  저장 완료: {total:,}건")
        else:
            results[table_name] = 0
            print(f"  수집된 데이터 없음")

        # API 호출 간격
        if i < len(targets):
            time.sleep(1)

    # 최종 요약
    print(f"\n{'=' * 60}")
    print("수집 완료")
    print("=" * 60)
    for table_name, count in results.items():
        print(f"  {table_name}: {count:,}건")
    print("=" * 60)


if __name__ == "__main__":
    main()
