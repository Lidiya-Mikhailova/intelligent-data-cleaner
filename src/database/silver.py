from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)


def _valid_table_name(source_file: str) -> str:
    return f"silver_valid_{Path(source_file).stem}"


def _invalid_table_name(source_file: str) -> str:
    return f"silver_invalid_{Path(source_file).stem}"


def _quarantine_table_name(source_file: str) -> str:
    return f"silver_quarantine_{Path(source_file).stem}"


def get_silver_tables(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return conn.execute("SELECT * FROM silver_tables ORDER BY cleaned_at DESC").fetchdf()


def get_silver_data(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
) -> pd.DataFrame:
    return conn.execute(f"SELECT * FROM {table_name}").fetchdf()


def _append_table(conn: duckdb.DuckDBPyConnection, tbl: str, df: pd.DataFrame) -> None:
    """Append DataFrame to a table (create if not exists)."""
    if df.empty:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {tbl} (dummy VARCHAR)")
        return
    conn.register("_vw", df)
    conn.execute(f"CREATE TABLE IF NOT EXISTS {tbl} AS SELECT * FROM _vw WHERE FALSE")
    conn.execute(f"INSERT INTO {tbl} SELECT * FROM _vw")
    conn.unregister("_vw")


def write_silver(
    conn: duckdb.DuckDBPyConnection,
    valid_df: pd.DataFrame,
    invalid_df: pd.DataFrame,
    quarantine_df: pd.DataFrame,
    source_file: str,
    dedup_count: int = 0,
    pipeline_run_id: int = 0,
    processing_stages: Optional[list[dict]] = None,
) -> tuple[str, int, int, int, int]:
    """
    Write pre-classified records to Silver layer tables (append-only).

    Data must already be classified by ``core.validation.classify_records()``.

    Returns:
        (valid_table_name, valid_count, invalid_count, quarantine_count, dedup_count)
    """
    valid_tbl = _valid_table_name(source_file)
    invalid_tbl = _invalid_table_name(source_file)
    quarantine_tbl = _quarantine_table_name(source_file)

    if valid_df.empty and invalid_df.empty and quarantine_df.empty:
        return "", 0, 0, 0, dedup_count

    _append_table(conn, valid_tbl, valid_df)
    _append_table(conn, invalid_tbl, invalid_df)
    _append_table(conn, quarantine_tbl, quarantine_df)

    valid_count = len(valid_df)
    invalid_count = len(invalid_df)
    quarantine_count = len(quarantine_df)

    stages_json = json.dumps(processing_stages or [])

    conn.execute(
        """
        INSERT INTO silver_tables
            (id, pipeline_run_id, source_file, table_name, row_count, column_count, dedup_count, processing_stages)
        SELECT
            nextval('global_seq'),
            $1, $2, $3, $4, $5, $6, $7
    """,
        [
            pipeline_run_id,
            source_file,
            valid_tbl,
            valid_count,
            len(valid_df.columns) if not valid_df.empty else 0,
            dedup_count,
            stages_json,
        ],
    )

    if quarantine_count > 0:
        conn.execute(
            """
            INSERT INTO silver_quarantine (id, pipeline_run_id, source_file, table_name, row_count)
            SELECT
                nextval('global_seq'),
                $1, $2, $3, $4
        """,
            [pipeline_run_id, source_file, quarantine_tbl, quarantine_count],
        )

    conn.commit()
    logger.info(
        "Silver appended: %s -> valid: %s (+%d), invalid: %s (+%d), quarantine: %s (+%d), deduped: %d",
        source_file,
        valid_tbl,
        valid_count,
        invalid_tbl,
        invalid_count,
        quarantine_tbl,
        quarantine_count,
        dedup_count,
    )
    return valid_tbl, valid_count, invalid_count, quarantine_count, dedup_count
