"""
DuckDB 연결 관리 모듈
- 읽기 전용으로 기존 데이터베이스에 접근
"""
import os
from pathlib import Path

import duckdb
import pandas as pd
from src.config import DB_PATH


def database_path() -> Path:
    """챕터 8 대시보드가 사용할 DuckDB 경로를 반환한다."""
    return Path(os.environ.get("TRADE_MAP_DB_PATH") or DB_PATH).expanduser()


def get_connection() -> duckdb.DuckDBPyConnection:
    """DuckDB 읽기 전용 연결을 생성한다."""
    path = database_path()
    if not path.is_file():
        raise FileNotFoundError(
            "데이터베이스가 없습니다. TRADE_MAP_DB_PATH 또는 기본 DB 경로를 "
            f"확인하세요: {path}"
        )
    return duckdb.connect(str(path), read_only=True)


def get_table_columns(table_name: str) -> set[str]:
    """현재 DB의 테이블 컬럼명을 반환한다."""
    con = get_connection()
    try:
        rows = con.execute(
            """
            SELECT column_name
            FROM duckdb_columns()
            WHERE database_name = current_database()
              AND schema_name = 'main'
              AND table_name = ?
            """,
            [table_name],
        ).fetchall()
        return {row[0] for row in rows}
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
