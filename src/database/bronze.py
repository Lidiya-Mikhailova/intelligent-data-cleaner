from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)


def _table_name(filename: str) -> str:
    return f"bronze_{Path(filename).stem}"


def register_bronze(
    conn: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    filename: str,
    pipeline_run_id: int = 0,
) -> str:
    """
    Register data in the Bronze layer (append-only).

    Creates or appends to the bronze table and logs metadata.
    Returns the table name.
    """
    tbl = _table_name(filename)

    if not df.empty:
        conn.register("df_view", df)
        conn.execute(f"CREATE TABLE IF NOT EXISTS {tbl} AS SELECT * FROM df_view WHERE FALSE")
        conn.execute(f"INSERT INTO {tbl} SELECT * FROM df_view")
        conn.unregister("df_view")

    conn.execute(
        """
        INSERT INTO bronze_files (id, pipeline_run_id, filename, suffix, file_size, row_count, column_count)
        SELECT
            nextval('global_seq'),
            $1, $2, $3, $4, $5, $6
    """,
        [pipeline_run_id, filename, Path(filename).suffix, 0, len(df), len(df.columns) if not df.empty else 0],
    )

    conn.commit()
    logger.info("Bronze appended: %s -> %s (+%d rows)", filename, tbl, len(df))
    return tbl
