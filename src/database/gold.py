from __future__ import annotations

import logging

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)


def write_gold(
    conn: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    table_name: str,
    source_tables: list[str],
    description: str = "",
    pipeline_run_id: int = 0,
) -> str:
    """
    Write final structured dataset to gold layer (append-only).

    Only clean, validated data should be written to gold.
    Creates the gold table on first write, appends on subsequent writes.
    Tracks all runs in the gold_tables metadata table.
    Returns the gold table name.
    """
    if df.empty:
        return ""

    tbl = f"gold_{table_name}"

    conn.register("gold_view", df)
    conn.execute(f"CREATE TABLE IF NOT EXISTS {tbl} AS SELECT * FROM gold_view WHERE FALSE")
    conn.execute(f"INSERT INTO {tbl} SELECT * FROM gold_view")
    conn.unregister("gold_view")

    conn.execute(
        """
        INSERT INTO gold_tables (id, pipeline_run_id, table_name, source_tables, row_count, column_count, description)
        SELECT
            nextval('global_seq'),
            $1, $2, $3, $4, $5, $6
    """,
        [pipeline_run_id, tbl, ",".join(source_tables), len(df), len(df.columns), description],
    )

    conn.commit()
    logger.info("Gold appended: %s (+%d rows)", tbl, len(df))
    return tbl


def get_gold_tables(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """List all gold tables with metadata."""
    return conn.execute("SELECT * FROM gold_tables ORDER BY created_at DESC").fetchdf()


def get_gold_data(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
) -> pd.DataFrame:
    """Get data from a gold table."""
    return conn.execute(f"SELECT * FROM {table_name}").fetchdf()
