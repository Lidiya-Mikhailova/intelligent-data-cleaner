from __future__ import annotations

import logging

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)


def read_table(conn: duckdb.DuckDBPyConnection, table_name: str) -> pd.DataFrame:
    """Read data from a database table. Pure storage operation."""
    return conn.execute(f"SELECT * FROM {table_name}").fetchdf()
