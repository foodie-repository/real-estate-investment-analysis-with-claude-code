"""
DuckDB 연결 관리 모듈

KB 통계와 매매 실거래가 모두 동일한 DuckDB에서 조회한다.
DB 경로는 환경변수 KB_DB_PATH로 오버라이드할 수 있다.
"""
import os

import duckdb
import pandas as pd
from dotenv import load_dotenv
from src.config import DB_PATH

load_dotenv()

# 기본값: 프로젝트 DB. 환경변수로 오버라이드 가능.
_DB_PATH = os.getenv("KB_DB_PATH", DB_PATH)


def get_connection() -> duckdb.DuckDBPyConnection:
    """DuckDB 읽기 전용 연결을 생성한다."""
    return duckdb.connect(_DB_PATH, read_only=True)


def relation_exists(name: str) -> bool:
    """테이블 또는 뷰가 존재하는지 확인한다."""
    con = get_connection()
    try:
        row = con.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = ?
            LIMIT 1
            """,
            [name],
        ).fetchone()
        return row is not None
    finally:
        con.close()


def execute_query(query: str, params: list | None = None) -> pd.DataFrame:
    """쿼리를 실행하고 DataFrame으로 반환한다."""
    con = get_connection()
    try:
        if params is not None:
            return con.execute(query, params).fetchdf()
        return con.execute(query).fetchdf()
    finally:
        con.close()
