"""
아파트 실거래가 수집 모듈

공공데이터포털 API에서 아파트 매매/전월세 실거래가 데이터를 수집하여
DuckDB에 저장한다.

사용법:
    python -m src.collectors.실거래가 --year 2024
    python -m src.collectors.실거래가 --year 2024 --sido 서울특별시
    python -m src.collectors.실거래가 --year 2024 --type 매매
"""

import argparse
import sys
import duckdb
import pandas as pd
from PublicDataReader import TransactionPrice, code_bdong
from src.config import DB_PATH, PUBLIC_DATA_API_KEY


# ──────────────────────────────────────────────
# 시군구 코드 목록 조회
# ──────────────────────────────────────────────
def get_sigungu_codes(sido=None):
    """
    전국 시군구 코드 목록을 가져온다.
    sido를 지정하면 해당 시도의 시군구만 반환한다.
    """
    bdong = code_bdong()

    # 시군구 단위만 추출 (시군구명이 비어있지 않은 행)
    sigungu = bdong[bdong["시군구명"] != ""][
        ["시군구코드", "시도명", "시군구명"]
    ].drop_duplicates()

    if sido:
        sigungu = sigungu[sigungu["시도명"] == sido]
        if len(sigungu) == 0:
            print(f"오류: '{sido}'에 해당하는 시도를 찾을 수 없습니다.")
            sys.exit(1)

    return sigungu.reset_index(drop=True)


# ──────────────────────────────────────────────
# 도로명 건물번호 조합
# ──────────────────────────────────────────────
def build_road_address(row, road_col, bonbun_col, bubun_col):
    """
    도로명과 건물번호를 합쳐서 완성된 도로명주소를 만든다.
    예: "헌릉로590길" + 63 + 0 → "헌릉로590길 63"
    예: "헌릉로590길" + 63 + 5 → "헌릉로590길 63-5"
    """
    road = row.get(road_col, "")
    if pd.isna(road) or road == "":
        return ""

    # 건물 본번호 (0이 아닌 경우만)
    bonbun = row.get(bonbun_col, "00000")
    if pd.isna(bonbun) or str(bonbun).strip().lower() == "none":
        bonbun = "00000"
    bonbun_num = int(str(bonbun).strip())

    if bonbun_num == 0:
        return str(road).strip()

    # 건물 부번호 (0이 아닌 경우 "-부번호" 추가)
    bubun = row.get(bubun_col, "00000")
    if pd.isna(bubun) or str(bubun).strip().lower() == "none":
        bubun = "00000"
    bubun_num = int(str(bubun).strip())

    if bubun_num > 0:
        return f"{road} {bonbun_num}-{bubun_num}"
    else:
        return f"{road} {bonbun_num}"


# ──────────────────────────────────────────────
# 매매 데이터 수집 및 가공
# ──────────────────────────────────────────────
def collect_매매(api, sigungu_codes, year):
    """매매 실거래가 데이터를 시군구별로 수집한다."""
    all_data = []
    errors = []
    total = len(sigungu_codes)

    for idx, row in sigungu_codes.iterrows():
        code = row["시군구코드"]
        sido = row["시도명"]
        sigungu = row["시군구명"]
        print(f"  [{idx + 1}/{total}] {sido} {sigungu}", end=" ... ")

        try:
            df = api.get_data(
                property_type="아파트",
                trade_type="매매",
                sigungu_code=code,
                start_year_month=f"{year}01",
                end_year_month=f"{year}12",
            )

            if df is not None and len(df) > 0:
                # 시군구 컬럼: "서울특별시 강남구 대치동" 형태
                df["시군구"] = sido + " " + sigungu + " " + df["법정동"]

                # 계약년월: 202401 형태 (BIGINT)
                df["계약년월"] = df["계약년도"] * 100 + df["계약월"]

                # 도로명: 도로명 + 건물번호 조합
                df["도로명"] = df.apply(
                    lambda r: build_road_address(
                        r, "도로명", "도로명건물본번호코드", "도로명건물부번호코드"
                    ),
                    axis=1,
                )

                all_data.append(df)
                print(f"{len(df):,}건")
            else:
                print("없음")

        except Exception as e:
            errors.append(f"{sido} {sigungu}: {e}")
            print(f"오류")

    if not all_data:
        return pd.DataFrame(), errors

    result = pd.concat(all_data, ignore_index=True)

    # 최종 컬럼 선택 및 정리
    columns = {
        "시군구": "시군구",
        "번지": "지번",
        "단지명": "단지명",
        "전용면적": "전용면적",
        "계약년월": "계약년월",
        "계약일": "계약일",
        "거래금액": "거래금액",
        "층": "층",
        "건축년도": "건축년도",
        "도로명": "도로명",
        "매수자": "매수자",
        "매도자": "매도자",
        "해제사유발생일": "해제사유발생일",
        "거래유형": "거래유형",
    }

    # 존재하는 컬럼만 선택
    available = [c for c in columns.keys() if c in result.columns]
    result = result[available].rename(
        columns={k: v for k, v in columns.items() if k in available}
    )

    return result, errors


# ──────────────────────────────────────────────
# 전월세 데이터 수집 및 가공
# ──────────────────────────────────────────────
def collect_전월세(api, sigungu_codes, year):
    """전월세 실거래가 데이터를 시군구별로 수집한다."""
    all_data = []
    errors = []
    total = len(sigungu_codes)

    for idx, row in sigungu_codes.iterrows():
        code = row["시군구코드"]
        sido = row["시도명"]
        sigungu = row["시군구명"]
        print(f"  [{idx + 1}/{total}] {sido} {sigungu}", end=" ... ")

        try:
            df = api.get_data(
                property_type="아파트",
                trade_type="전월세",
                sigungu_code=code,
                start_year_month=f"{year}01",
                end_year_month=f"{year}12",
            )

            if df is not None and len(df) > 0:
                # 시군구 컬럼
                df["시군구"] = sido + " " + sigungu + " " + df["법정동"]

                # 계약년월
                df["계약년월"] = df["계약년도"] * 100 + df["계약월"]

                # 전월세구분: 월세금액이 0이면 "전세", 아니면 "월세"
                df["전월세구분"] = df["월세금액"].apply(
                    lambda x: "전세" if pd.notna(x) and float(x) == 0 else "월세"
                )

                # 도로명: roadnm은 이미 건물번호를 포함하고 있음
                # 예: "삼성로 212", "삼성로51길 25"
                df["도로명"] = df["roadnm"].fillna("")

                all_data.append(df)
                print(f"{len(df):,}건")
            else:
                print("없음")

        except Exception as e:
            errors.append(f"{sido} {sigungu}: {e}")
            print(f"오류")

    if not all_data:
        return pd.DataFrame(), errors

    result = pd.concat(all_data, ignore_index=True)

    # 최종 컬럼 선택 및 정리
    columns = {
        "시군구": "시군구",
        "단지명": "단지명",
        "전월세구분": "전월세구분",
        "전용면적": "전용면적",
        "계약년월": "계약년월",
        "계약일": "계약일",
        "보증금액": "보증금",
        "월세금액": "월세금",
        "층": "층",
        "건축년도": "건축년도",
        "도로명": "도로명",
        "계약기간": "계약기간",
        "계약구분": "계약구분",
        "갱신요구권사용": "갱신요구권사용",
    }

    available = [c for c in columns.keys() if c in result.columns]
    result = result[available].rename(
        columns={k: v for k, v in columns.items() if k in available}
    )

    return result, errors


# ──────────────────────────────────────────────
# DuckDB 저장
# ──────────────────────────────────────────────
def save_to_duckdb(df, table_name, year):
    """
    DuckDB에 저장한다.
    같은 연도 데이터가 있으면 삭제 후 재저장 (중복 방지).
    """
    con = duckdb.connect(DB_PATH)

    # 테이블 존재 여부 확인
    tables = [
        t[0]
        for t in con.execute(
            "SELECT table_name FROM information_schema.tables"
        ).fetchall()
    ]

    if table_name in tables:
        # 해당 연도 데이터 삭제
        con.execute(
            f'DELETE FROM "{table_name}" '
            f"WHERE 계약년월 >= {year}01 AND 계약년월 <= {year}12"
        )
        # 새 데이터 추가
        con.execute(f'INSERT INTO "{table_name}" SELECT * FROM df')
    else:
        # 테이블 새로 생성
        con.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM df')

    total = con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
    con.close()
    return total


# ──────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="아파트 실거래가 수집")
    parser.add_argument("--year", type=int, required=True, help="수집 연도 (예: 2024)")
    parser.add_argument("--sido", type=str, help="특정 시도만 수집 (예: 서울특별시)")
    parser.add_argument(
        "--type", type=str, choices=["매매", "전월세"], help="특정 유형만 수집"
    )
    args = parser.parse_args()

    # API 초기화
    if not PUBLIC_DATA_API_KEY:
        print("오류: .env 파일에 PUBLIC_DATA_API_KEY를 설정하세요.")
        sys.exit(1)

    api = TransactionPrice(PUBLIC_DATA_API_KEY)

    # 시군구 코드 목록
    sigungu_codes = get_sigungu_codes(args.sido)

    # 수집 대상 유형
    trade_types = [args.type] if args.type else ["매매", "전월세"]

    print("=" * 60)
    print("아파트 실거래가 수집")
    print("=" * 60)
    print(f"수집 연도: {args.year}")
    print(f"수집 대상: {', '.join(trade_types)}")
    print(f"시군구 수: {len(sigungu_codes)}개")
    if args.sido:
        print(f"시도 필터: {args.sido}")
    print("=" * 60)

    results = {}

    for trade_type in trade_types:
        print(f"\n[{trade_type}] 수집 시작")
        print("-" * 40)

        if trade_type == "매매":
            df, errors = collect_매매(api, sigungu_codes, args.year)
        else:
            df, errors = collect_전월세(api, sigungu_codes, args.year)

        if len(df) > 0:
            total = save_to_duckdb(df, trade_type, args.year)
            results[trade_type] = {"수집": len(df), "전체": total, "오류": len(errors)}
            print(f"\n  저장 완료: {len(df):,}건 (테이블 전체: {total:,}건)")
        else:
            results[trade_type] = {"수집": 0, "전체": 0, "오류": len(errors)}
            print(f"\n  수집된 데이터 없음")

        if errors:
            print(f"  오류: {len(errors)}건")

    # 최종 요약
    print(f"\n{'=' * 60}")
    print("수집 완료")
    print("=" * 60)
    for name, info in results.items():
        print(f"  {name}: {info['수집']:,}건 수집, {info['오류']}건 오류")
    print("=" * 60)


if __name__ == "__main__":
    main()
