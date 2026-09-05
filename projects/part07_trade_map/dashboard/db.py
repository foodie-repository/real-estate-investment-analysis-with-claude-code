"""
DuckDB 연결 관리 모듈
- 읽기 전용으로 기존 데이터베이스에 접근
"""
import duckdb
import pandas as pd
from src.config import DB_PATH


def get_connection() -> duckdb.DuckDBPyConnection:
    """DuckDB 읽기 전용 연결을 생성한다."""
    return duckdb.connect(DB_PATH, read_only=True)


def execute_query(query: str, params: list | None = None) -> pd.DataFrame:
    """쿼리를 실행하고 DataFrame으로 반환한다."""
    con = get_connection()
    try:
        if params is not None:
            return con.execute(query, params).fetchdf()
        return con.execute(query).fetchdf()
    finally:
        con.close()
