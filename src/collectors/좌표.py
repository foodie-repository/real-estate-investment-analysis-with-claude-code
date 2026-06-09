"""
좌표 데이터 수집 모듈

카카오 Geocoding API로 아파트 도로명주소를 위도·경도 좌표로 변환하여
DuckDB에 저장한다.

이 좌표 데이터는 Part09 거래량 지도에서 아파트 단지 위치에
마커를 표시할 때 사용된다.

사용법:
    python -m src.collectors.좌표
    python -m src.collectors.좌표 --sido 서울특별시
"""

import argparse
import sys
import time
import duckdb
import pandas as pd
import requests
from src.config import DB_PATH, KAKAO_API_KEY
from src.utils.address import ROAD_ADDRESS_KEY_SQL


_ADDRESS_BASE_FILTER = """
    시군구 IS NOT NULL
    AND 도로명 IS NOT NULL
    AND TRIM(CAST(도로명 AS VARCHAR)) NOT IN ('', 'None', '-')
"""
_TRADE_TABLES = ("매매", "전월세")


def _list_tables(con) -> set[str]:
    """현재 DuckDB 파일에 있는 테이블명 목록을 반환한다."""
    rows = con.execute("SELECT table_name FROM information_schema.tables").fetchall()
    return {row[0] for row in rows}


def _build_address_union_query(
    tables: set[str],
    sido: str | None = None,
    include_legacy_road: bool = False,
) -> tuple[str, list]:
    """
    매매/전월세 테이블에서 도로명주소 키를 추출하는 UNION 쿼리를 만든다.

    include_legacy_road=True이면 기존 도로명 단독 좌표 backfill을 위해
    원본 도로명 컬럼도 함께 반환한다.
    """
    query_parts = []
    params = []

    for table in _TRADE_TABLES:
        if table not in tables:
            continue

        where = _ADDRESS_BASE_FILTER
        if sido:
            where += " AND 시군구 LIKE ?"
            params.append(f"{sido}%")

        if include_legacy_road:
            select_clause = f"도로명, {ROAD_ADDRESS_KEY_SQL} AS 도로명주소"
        else:
            select_clause = f"{ROAD_ADDRESS_KEY_SQL} AS 도로명주소"

        query_parts.append(f"""
            SELECT DISTINCT {select_clause}
            FROM {table}
            WHERE {where}
        """)

    return " UNION ".join(query_parts), params


# ──────────────────────────────────────────────
# 변환 대상 주소 추출
# ──────────────────────────────────────────────
def get_addresses_to_geocode(sido=None):
    """
    매매, 전월세 테이블에서 고유 도로명주소 키 목록을 추출한다.
    이미 좌표 테이블에 있는 주소는 제외한다 (증분 수집).
    """
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        tables = _list_tables(con)
        union_query, params = _build_address_union_query(tables, sido)

        if not union_query:
            return []

        # 이미 좌표가 있는 주소 제외
        if "좌표" in tables:
            final_query = f"""
                SELECT 도로명주소
                FROM ({union_query})
                WHERE 도로명주소 IS NOT NULL
                  AND 도로명주소 != ''
                  AND 도로명주소 NOT IN (
                      SELECT 도로명주소 FROM 좌표 WHERE 도로명주소 IS NOT NULL
                  )
            """
        else:
            final_query = f"""
                SELECT 도로명주소
                FROM ({union_query})
                WHERE 도로명주소 IS NOT NULL
                  AND 도로명주소 != ''
            """

        addresses = con.execute(final_query, params).fetchall()
    finally:
        con.close()

    return [a[0] for a in addresses if a[0]]


def backfill_region_qualified_coordinates_from_legacy(sido=None):
    """
    예전 도로명 단독 좌표를 새 도로명주소 키로 안전하게 복사한다.

    같은 도로명이 여러 지역에 연결되는 경우에는 오좌표 위험이 있으므로
    복사하지 않고 지오코딩 대상으로 남긴다.
    """
    con = duckdb.connect(DB_PATH)
    try:
        tables = _list_tables(con)

        if "좌표" not in tables:
            return 0

        union_query, params = _build_address_union_query(
            tables,
            sido,
            include_legacy_road=True,
        )
        if not union_query:
            return 0

        con.execute("DROP TABLE IF EXISTS _coordinate_backfill")
        con.execute(f"""
            CREATE TEMP TABLE _coordinate_backfill AS
            WITH source_keys AS (
                {union_query}
            ),
            safe_keys AS (
                SELECT
                    도로명,
                    MIN(도로명주소) AS 도로명주소
                FROM source_keys
                WHERE 도로명주소 IS NOT NULL
                  AND 도로명주소 != ''
                GROUP BY 도로명
                HAVING COUNT(DISTINCT 도로명주소) = 1
            ),
            legacy_coords AS (
                SELECT
                    도로명주소 AS 도로명,
                    FIRST(경도) AS 경도,
                    FIRST(위도) AS 위도
                FROM 좌표
                WHERE 도로명주소 IS NOT NULL
                  AND 경도 IS NOT NULL
                  AND 위도 IS NOT NULL
                GROUP BY 도로명주소
            )
            SELECT
                s.도로명주소,
                l.경도,
                l.위도
            FROM safe_keys s
            JOIN legacy_coords l ON s.도로명 = l.도로명
            WHERE NOT EXISTS (
                SELECT 1
                FROM 좌표 z
                WHERE z.도로명주소 = s.도로명주소
            )
        """, params)

        inserted = con.execute("SELECT COUNT(*) FROM _coordinate_backfill").fetchone()[0]
        if inserted:
            con.execute('INSERT INTO "좌표" SELECT 도로명주소, 경도, 위도 FROM _coordinate_backfill')

        con.execute("DROP TABLE IF EXISTS _coordinate_backfill")
    finally:
        con.close()

    return inserted


# ──────────────────────────────────────────────
# 카카오 Geocoding API 호출
# ──────────────────────────────────────────────
def geocode_address(address, api_key):
    """
    카카오 Geocoding API로 주소를 좌표로 변환한다.
    성공하면 (경도, 위도) 튜플, 실패하면 None을 반환한다.
    """
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {"query": address}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        response.raise_for_status()
        result = response.json()

        if result["documents"]:
            doc = result["documents"][0]
            return float(doc["x"]), float(doc["y"])

    except Exception:
        pass

    return None


# ──────────────────────────────────────────────
# 좌표 일괄 변환
# ──────────────────────────────────────────────
def geocode_batch(addresses, api_key, sleep_time=0.05):
    """
    주소 목록을 일괄 변환한다.
    API 호출 간격을 조절해서 차단을 방지한다.
    """
    results = []
    total = len(addresses)
    success = 0
    fail = 0

    for i, address in enumerate(addresses):
        coord = geocode_address(address, api_key)

        if coord:
            results.append({
                "도로명주소": address,
                "경도": coord[0],
                "위도": coord[1],
            })
            success += 1
        else:
            fail += 1

        # 진행 상황 출력 (1000건마다)
        if (i + 1) % 1000 == 0 or (i + 1) == total:
            print(f"  진행: {i + 1:,}/{total:,} ({(i + 1) * 100 / total:.1f}%)")

        # API 호출 간격 조절
        time.sleep(sleep_time)

    return pd.DataFrame(results), success, fail


# ──────────────────────────────────────────────
# DuckDB 저장 (증분 추가)
# ──────────────────────────────────────────────
def save_to_duckdb(df):
    """
    DuckDB 좌표 테이블에 추가한다.
    테이블이 없으면 새로 생성하고, 있으면 데이터를 추가한다.
    """
    con = duckdb.connect(DB_PATH)

    tables = [t[0] for t in con.execute(
        "SELECT table_name FROM information_schema.tables"
    ).fetchall()]

    if "좌표" in tables:
        con.execute('INSERT INTO "좌표" SELECT * FROM df')
    else:
        con.execute('CREATE TABLE "좌표" AS SELECT * FROM df')

    total = con.execute('SELECT COUNT(*) FROM "좌표"').fetchone()[0]
    con.close()
    return total


# ──────────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="좌표 데이터 수집 (카카오 Geocoding)")
    parser.add_argument("--sido", type=str, help="특정 시도만 수집 (예: 서울특별시)")
    args = parser.parse_args()

    if not KAKAO_API_KEY:
        print("오류: .env 파일에 KAKAO_API_KEY를 설정하세요.")
        sys.exit(1)

    print("=" * 60)
    print("좌표 데이터 수집 (카카오 Geocoding API)")
    print("=" * 60)

    reused = backfill_region_qualified_coordinates_from_legacy(args.sido)
    if reused:
        print(f"기존 좌표 재활용: {reused:,}건")

    # 변환 대상 주소 추출
    addresses = get_addresses_to_geocode(args.sido)

    if not addresses:
        print("변환할 주소가 없습니다 (이미 모두 수집됨).")
        return

    print(f"변환 대상 주소: {len(addresses):,}건 (이미 수집된 주소 제외)")

    # 일괄 변환
    df, success, fail = geocode_batch(addresses, KAKAO_API_KEY)

    if len(df) > 0:
        total = save_to_duckdb(df)

        print(f"\n{'=' * 60}")
        print("수집 완료")
        print("=" * 60)
        print(f"  성공: {success:,}건")
        print(f"  실패: {fail:,}건 (주소 미매칭)")
        print(f"  총 좌표 수: {total:,}건")
        print("=" * 60)
    else:
        print("\n변환된 좌표가 없습니다.")


if __name__ == "__main__":
    main()
