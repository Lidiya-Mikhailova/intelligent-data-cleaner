from __future__ import annotations

from pathlib import Path

import duckdb


def get_db_path(base_dir: Path) -> Path:
    """Return the path to the DuckDB database file."""
    db_dir = base_dir / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "data_cleaner.duckdb"


def get_conn(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Get a DuckDB connection."""
    return duckdb.connect(str(db_path))


def init_db(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Initialize database schema and return connection."""
    conn = get_conn(db_path)

    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS global_seq START 1
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id              INTEGER PRIMARY KEY,
            source_file     VARCHAR,
            source_format   VARCHAR,
            started_at      TIMESTAMP DEFAULT now(),
            completed_at    TIMESTAMP,
            stages          VARCHAR DEFAULT '[]',
            row_counts      VARCHAR DEFAULT '{}',
            status          VARCHAR DEFAULT 'running',
            error_message   VARCHAR DEFAULT ''
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bronze_files (
            id              INTEGER PRIMARY KEY,
            pipeline_run_id INTEGER,
            filename        VARCHAR,
            suffix          VARCHAR,
            file_size       BIGINT,
            row_count       BIGINT,
            column_count    INTEGER,
            ingested_at     TIMESTAMP DEFAULT now(),
            status          VARCHAR DEFAULT 'raw'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS silver_tables (
            id                INTEGER PRIMARY KEY,
            pipeline_run_id   INTEGER,
            source_file       VARCHAR,
            table_name        VARCHAR,
            row_count         BIGINT,
            column_count      INTEGER,
            cleaned_at        TIMESTAMP DEFAULT now(),
            dedup_count       BIGINT DEFAULT 0,
            processing_stages VARCHAR DEFAULT '[]'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS silver_quarantine (
            id              INTEGER PRIMARY KEY,
            pipeline_run_id INTEGER,
            source_file     VARCHAR,
            table_name      VARCHAR,
            row_count       BIGINT,
            created_at      TIMESTAMP DEFAULT now()
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS gold_tables (
            id              INTEGER,
            pipeline_run_id INTEGER,
            table_name      VARCHAR PRIMARY KEY,
            source_tables   VARCHAR,
            row_count       BIGINT,
            column_count    INTEGER,
            created_at      TIMESTAMP DEFAULT now(),
            description     VARCHAR DEFAULT ''
        )
    """)

    conn.commit()
    return conn
