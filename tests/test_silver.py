import duckdb
import pandas as pd
import pytest

from src.core.validation import classify_records
from src.database.silver import _invalid_table_name, _valid_table_name, write_silver


@pytest.fixture
def conn():
    db = duckdb.connect(":memory:")
    db.execute("""
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
    db.execute("CREATE SEQUENCE IF NOT EXISTS global_seq START 1")
    db.execute("""
        CREATE TABLE IF NOT EXISTS silver_quarantine (
            id              INTEGER PRIMARY KEY,
            pipeline_run_id INTEGER,
            source_file     VARCHAR,
            table_name      VARCHAR,
            row_count       BIGINT,
            created_at      TIMESTAMP DEFAULT now()
        )
    """)
    db.commit()
    yield db
    db.close()


def test_table_names():
    assert _valid_table_name("test.csv") == "silver_valid_test"
    assert _invalid_table_name("data.txt") == "silver_invalid_data"
    assert _valid_table_name("path/to/file.csv") == "silver_valid_file"


def _write(conn, df, source_file, **kwargs):
    valid_df, invalid_df, quarantine_df = classify_records(df)
    return write_silver(conn, valid_df, invalid_df, quarantine_df, source_file, **kwargs)


def test_write_silver_all_valid(conn):
    df = pd.DataFrame(
        {
            "ID": [1, 2],
            "Name": ["Alice", "Bob"],
            "Age": [30, 25],
            "Email": ["alice@example.com", "bob@example.com"],
            "Address": ["Addr1", "Addr2"],
            "Notes": ["Note1", "Note2"],
        }
    )
    tbl, v, inv, q, dedup = _write(conn, df, "test.csv")
    assert tbl == "silver_valid_test"
    assert v == 2
    assert inv == 0
    assert q == 0
    assert dedup >= 0

    result = conn.execute("SELECT * FROM silver_valid_test").fetchdf()
    assert len(result) == 2


def test_write_silver_some_invalid(conn):
    df = pd.DataFrame(
        {
            "ID": [1, 2, 3],
            "Name": ["Alice", "", "Charlie"],
            "Age": [30, 25, 50],
            "Email": ["a@b.com", "c@d.com", "e@f.com"],
            "Address": ["", "", ""],
            "Notes": ["", "", ""],
        }
    )
    tbl, v, inv, q, dedup = _write(conn, df, "people.csv")
    assert v == 2
    assert inv == 1
    assert q == 0
    assert tbl == "silver_valid_people"

    valid = conn.execute("SELECT * FROM silver_valid_people").fetchdf()
    assert len(valid) == 2
    assert "Alice" in valid["Name"].values
    assert "Charlie" in valid["Name"].values

    invalid = conn.execute("SELECT * FROM silver_invalid_people").fetchdf()
    assert len(invalid) == 1
    assert "validation_error" in invalid.columns


def test_write_silver_empty_df(conn):
    df = pd.DataFrame()
    valid_df, invalid_df, quarantine_df = classify_records(df)
    tbl, v, inv, q, dedup = write_silver(conn, valid_df, invalid_df, quarantine_df, "empty.csv")
    assert tbl == ""
    assert v == 0
    assert inv == 0
    assert q == 0
    assert dedup == 0


def test_write_silver_empty_age_valid(conn):
    df = pd.DataFrame(
        {
            "ID": [1],
            "Name": ["Anna"],
            "Age": [""],
            "Email": ["anna@example.com"],
            "Address": ["addr"],
            "Notes": [""],
        }
    )
    tbl, v, inv, q, dedup = _write(conn, df, "test.csv")
    assert v == 1
    assert inv == 0
    assert q == 0


def test_write_silver_idn_email_valid(conn):
    df = pd.DataFrame(
        {
            "ID": [1],
            "Name": ["User"],
            "Age": [25],
            "Email": ["user@тест.рф"],
            "Address": [""],
            "Notes": [""],
        }
    )
    tbl, v, inv, q, dedup = _write(conn, df, "test.csv")
    assert v == 1
    assert inv == 0
    assert q == 0


def test_write_silver_negative_age_invalid(conn):
    df = pd.DataFrame(
        {
            "ID": [1],
            "Name": ["Bad"],
            "Age": [-5],
            "Email": [""],
            "Address": [""],
            "Notes": [""],
        }
    )
    tbl, v, inv, q, dedup = _write(conn, df, "test.csv")
    assert v == 0
    assert inv == 1
    assert q == 0


def test_write_silver_overage_invalid(conn):
    df = pd.DataFrame(
        {
            "ID": [1],
            "Name": ["Old"],
            "Age": [200],
            "Email": [""],
            "Address": [""],
            "Notes": [""],
        }
    )
    tbl, v, inv, q, dedup = _write(conn, df, "test.csv")
    assert v == 0
    assert inv == 1
    assert q == 0


def test_write_silver_metadata_logged(conn):
    df = pd.DataFrame(
        {
            "ID": [1, 2],
            "Name": ["Alice", "Bob"],
            "Age": [20, 30],
            "Email": ["x@x.com", "y@y.com"],
            "Address": ["", ""],
            "Notes": ["", ""],
        }
    )
    _write(conn, df, "meta_test.csv")

    meta = conn.execute("SELECT * FROM silver_tables").fetchdf()
    assert len(meta) >= 1
    row = meta.iloc[-1]
    assert row["source_file"] == "meta_test.csv"
    assert "silver_valid_meta_test" in row["table_name"]
    assert row["row_count"] == 2


def test_write_silver_zero_age_quarantine(conn):
    df = pd.DataFrame(
        {
            "ID": [1, 2],
            "Name": ["Zero", "Normal"],
            "Age": [0, 25],
            "Email": ["z@z.com", "n@n.com"],
            "Address": ["", ""],
            "Notes": ["", ""],
        }
    )
    tbl, v, inv, q, dedup = _write(conn, df, "quarantine_test.csv")
    assert v == 1
    assert inv == 0
    assert q == 1
    assert tbl == "silver_valid_quarantine_test"

    quarantine = conn.execute("SELECT * FROM silver_quarantine_quarantine_test").fetchdf()
    assert len(quarantine) == 1
    assert "quarantine_reasons" in quarantine.columns

    meta = conn.execute("SELECT * FROM silver_quarantine").fetchdf()
    assert len(meta) >= 1
    assert meta.iloc[-1]["row_count"] == 1
