"""
DuckDB 연결 관리 모듈

매매·전월세 실거래가 데이터를 DuckDB에서 조회한다.
DB 경로는 환경변수 PRICE_DB_PATH로 오버라이드할 수 있다.

외부 DuckDB와 프로젝트 DB의 스키마 차이를 투명하게 처리한다.
- 프로젝트 DB: 전용면적(DOUBLE), 거래금액(BIGINT), 시군구(풀스트링)
- 외부 DuckDB: 전용면적(㎡)(DOUBLE), 거래금액(만원)(VARCHAR), 시도/시군구/읍면동 개별 컬럼
"""
import os

import duckdb
import pandas as pd
from src.config import DB_PATH

# 기본값: 프로젝트 DB. 환경변수로 오버라이드 가능.
_DB_PATH = os.getenv("PRICE_DB_PATH", DB_PATH)


def _needs_normalization(db_path: str) -> bool:
    """외부 DuckDB 스키마인지 확인한다 (전용면적(㎡) 컬럼 존재 여부로 판단)."""
    con = duckdb.connect(db_path, read_only=True)
    try:
        cols = {row[0] for row in con.execute("DESCRIBE 매매").fetchall()}
        return "전용면적(㎡)" in cols
    finally:
        con.close()


def get_connection() -> duckdb.DuckDBPyConnection:
    """
    DuckDB 연결을 생성한다.

    외부 DuckDB인 경우 in-memory DB에 ATTACH하고,
    정규화 VIEW를 생성하여 프로젝트 DB와 동일한 스키마로 접근한다.
    """
    if _needs_normalization(_DB_PATH):
        con = duckdb.connect(":memory:")
        con.execute(f"ATTACH '{_DB_PATH}' AS src (READ_ONLY)")

        # 매매 테이블: 컬럼명·타입 정규화 + 주소 풀스트링 재결합
        con.execute("""
        CREATE VIEW 매매 AS
        SELECT
            시도 || ' ' || 시군구 || ' ' || COALESCE(읍면동, '') AS 시군구,
            단지명,
            "전용면적(㎡)" AS 전용면적,
            CAST(REPLACE("거래금액(만원)", ',', '') AS BIGINT) AS 거래금액,
            계약년월, 층, 건축년도, 도로명, 해제사유발생일, 거래유형
        FROM src.매매
        """)

        # 전월세 테이블: 동일 패턴
        con.execute("""
        CREATE VIEW 전월세 AS
        SELECT
            시도 || ' ' || 시군구 || ' ' || COALESCE(읍면동, '') AS 시군구,
            단지명, 전월세구분,
            "전용면적(㎡)" AS 전용면적,
            CAST(REPLACE("보증금(만원)", ',', '') AS BIGINT) AS 보증금,
            계약년월, 층, 건축년도, 도로명
        FROM src.전월세
        """)

        return con
    else:
        return duckdb.connect(_DB_PATH, read_only=True)


def execute_query(query: str, params: list | None = None) -> pd.DataFrame:
    """쿼리를 실행하고 DataFrame으로 반환한다."""
    con = get_connection()
    try:
        if params is not None:
            return con.execute(query, params).fetchdf()
        return con.execute(query).fetchdf()
    finally:
        con.close()
