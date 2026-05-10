from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

STAGE_TABLE_PREFIX = "stage_"

# ── Pipeline Run Lifecycle ─────────────────────────────────────────


def _stage_table_name(stage_name: str, source_file: str) -> str:
    stem = Path(source_file).stem
    safe_stage = stage_name.replace("-", "_")
    return f"{STAGE_TABLE_PREFIX}{stem}_{safe_stage}"


def create_pipeline_run(
    conn: duckdb.DuckDBPyConnection,
    source_file: str,
    source_format: str = "",
) -> int:
    """Create a new pipeline run and return its ID."""
    run_id = conn.execute("SELECT nextval('global_seq')").fetchone()[0]
    conn.execute(
        """
        INSERT INTO pipeline_runs (id, source_file, source_format, status)
        VALUES ($1, $2, $3, 'running')
        """,
        [run_id, source_file, source_format],
    )
    conn.commit()
    logger.info("Pipeline run #%d started: %s", run_id, source_file)
    return run_id


def update_pipeline_stages(
    conn: duckdb.DuckDBPyConnection,
    run_id: int,
    stages: List[Dict[str, Any]],
    row_counts: Optional[Dict[str, Dict[str, int]]] = None,
) -> None:
    """Update pipeline run with stage information."""
    conn.execute(
        """
        UPDATE pipeline_runs
        SET stages = $1, row_counts = $2
        WHERE id = $3
        """,
        [json.dumps(stages), json.dumps(row_counts or {}), run_id],
    )
    conn.commit()


def complete_pipeline_run(
    conn: duckdb.DuckDBPyConnection,
    run_id: int,
    status: str = "completed",
    error_message: str = "",
) -> None:
    """Mark a pipeline run as completed or failed."""
    conn.execute(
        """
        UPDATE pipeline_runs
        SET status = $1, completed_at = $2, error_message = $3
        WHERE id = $4
        """,
        [status, datetime.now(), error_message, run_id],
    )
    conn.commit()
    logger.info("Pipeline run #%d %s", run_id, status)


def get_pipeline_run(
    conn: duckdb.DuckDBPyConnection,
    run_id: int,
) -> Optional[Dict[str, Any]]:
    """Get pipeline run details."""
    result = conn.execute("SELECT * FROM pipeline_runs WHERE id = $1", [run_id]).fetchdf()
    if result.empty:
        return None
    return result.iloc[0].to_dict()


# ── Stage Result Persistence (for replayability) ───────────────────


def save_stage_result(
    conn: duckdb.DuckDBPyConnection,
    stage_name: str,
    df: pd.DataFrame,
    source_file: str,
) -> str:
    """Persist a pipeline stage's output to DuckDB for later replay.

    Creates/replaces a table named ``stage_<stem>_<stage_name>``.
    Returns the table name.
    """
    tbl = _stage_table_name(stage_name, source_file)
    if df.empty:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {tbl} (dummy VARCHAR)")
        logger.debug("Stage result (empty) saved: %s", tbl)
        return tbl
    conn.register("_sr", df)
    conn.execute(f"CREATE OR REPLACE TABLE {tbl} AS SELECT * FROM _sr")
    conn.unregister("_sr")
    conn.commit()
    logger.debug("Stage result saved: %s (%d rows)", tbl, len(df))
    return tbl


def load_stage_result(
    conn: duckdb.DuckDBPyConnection,
    stage_name: str,
    source_file: str,
) -> Optional[pd.DataFrame]:
    """Load a previously persisted stage result for replay.

    Returns None if the stage result does not exist (not yet run).
    """
    tbl = _stage_table_name(stage_name, source_file)
    try:
        df = conn.execute(f"SELECT * FROM {tbl}").fetchdf()
        logger.info("Stage result loaded: %s (%d rows)", tbl, len(df))
        return df
    except (duckdb.CatalogException, Exception):
        logger.info("Stage result not found: %s (not yet run)", tbl)
        return None


def stage_result_exists(
    conn: duckdb.DuckDBPyConnection,
    stage_name: str,
    source_file: str,
) -> bool:
    """Check whether a persisted stage result exists."""
    tbl = _stage_table_name(stage_name, source_file)
    try:
        conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
        return True
    except Exception:
        return False


def list_available_stages(
    conn: duckdb.DuckDBPyConnection,
    source_file: str,
) -> List[str]:
    """List all stage names that have persisted results for the given source file."""
    stem = Path(source_file).stem
    prefix = f"{STAGE_TABLE_PREFIX}{stem}_"
    try:
        tables = conn.execute(
            f"SELECT table_name FROM information_schema.tables WHERE table_name LIKE '{prefix}%'"
        ).fetchdf()
        return [row["table_name"].replace(prefix, "") for _, row in tables.iterrows()]
    except Exception:
        return []
