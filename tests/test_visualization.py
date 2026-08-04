import pandas as pd
import pytest

from src.core.metadata import DocumentMetadata, ProcessingStep
from src.visualization import (
    RICH_AVAILABLE,
    generate_report,
    render_dataframe,
    render_diff,
    render_metadata,
    render_pipeline_report,
    render_processing_summary,
    render_table,
)


@pytest.fixture(autouse=True)
def _isolate_rich():
    yield


def _meta() -> DocumentMetadata:
    meta = DocumentMetadata(
        source="data.csv",
        source_format="csv",
        row_count=2,
        column_count=2,
        columns=["Name", "Age"],
    )
    meta.add_step(ProcessingStep(name="normalize", rows_before=3, rows_after=2))
    meta.add_step(ProcessingStep(name="deduplicate", rows_before=2, rows_after=2))
    return meta


def _df() -> pd.DataFrame:
    return pd.DataFrame({"Name": ["Alice", "Bob"], "Age": [30, 25]})


# render_table


def test_render_table_empty():
    assert render_table([]) == "[empty]"


def test_render_table_rich(monkeypatch):
    if not RICH_AVAILABLE:
        pytest.skip("rich not installed")
    out = render_table([{"Name": "Alice", "Age": 30}], title="People")
    assert "People" in out
    assert "Alice" in out


def test_render_table_fallback(monkeypatch):
    monkeypatch.setattr("src.visualization.RICH_AVAILABLE", False)
    data = [{"Name": "Alice"}, {"Name": "Bob"}, {"Name": "Carol"}]
    out = render_table(data, title="People", max_rows=2)
    assert "=== People ===" in out
    assert "Row 1" in out
    assert "... and 1 more rows" in out


# render_dataframe


def test_render_dataframe_empty():
    assert render_dataframe(pd.DataFrame()) == "[empty dataframe]"


def test_render_dataframe_rich(monkeypatch):
    if not RICH_AVAILABLE:
        pytest.skip("rich not installed")
    out = render_dataframe(_df(), title="Data")
    assert "Data" in out
    assert "Alice" in out


def test_render_dataframe_fallback(monkeypatch):
    monkeypatch.setattr("src.visualization.RICH_AVAILABLE", False)
    out = render_dataframe(_df())
    assert "Alice" in out
    assert "Age" in out


# render_metadata


def test_render_metadata_fallback(monkeypatch):
    monkeypatch.setattr("src.visualization.RICH_AVAILABLE", False)
    out = render_metadata(_meta())
    assert "=== Document Metadata ===" in out
    assert "data.csv" in out
    assert "csv" in out


def test_render_metadata_rich(monkeypatch):
    if not RICH_AVAILABLE:
        pytest.skip("rich not installed")
    out = render_metadata(_meta())
    assert "Document Metadata" in out
    assert "data.csv" in out


# render_diff


def test_render_diff_fallback(monkeypatch):
    monkeypatch.setattr("src.visualization.RICH_AVAILABLE", False)
    before = _df()
    after = _df().iloc[:1]
    out = render_diff(before, after, title="Diff")
    assert "=== Diff ===" in out
    assert "Before: 2 rows, 2 cols" in out
    assert "After:  1 rows, 2 cols" in out
    assert "Removed: 1 rows" in out


# render_processing_summary


def test_render_processing_summary_fallback(monkeypatch):
    monkeypatch.setattr("src.visualization.RICH_AVAILABLE", False)
    out = render_processing_summary(_meta())
    assert "=== Processing Summary ===" in out
    assert "normalize: 3 -> 2 [success]" in out


# render_pipeline_report


def test_render_pipeline_report_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr("src.visualization.RICH_AVAILABLE", False)
    out = render_pipeline_report(_meta(), _df(), output_paths=[tmp_path / "out.csv"])
    assert "=== Pipeline Report ===" in out
    assert "Processing Summary" in out
    assert "out.csv" in out


# generate_report


def test_generate_report_content(monkeypatch):
    monkeypatch.setattr("src.visualization.RICH_AVAILABLE", False)
    out = generate_report(_meta(), _df())
    assert "Document Processing Report" in out
    assert "Source:       data.csv" in out
    assert "normalize: 3 \u2192 2 rows" in out
    assert "Name: 2/2 non-empty" in out


def test_generate_report_validation_errors(monkeypatch):
    monkeypatch.setattr("src.visualization.RICH_AVAILABLE", False)
    errors = pd.DataFrame({"validation_error": ["Bad Name"]})
    out = generate_report(_meta(), _df(), validation_errors=errors)
    assert "Validation Errors" in out
    assert "Bad Name" in out


def test_generate_report_writes_file(monkeypatch, tmp_path):
    monkeypatch.setattr("src.visualization.RICH_AVAILABLE", False)
    out_path = tmp_path / "nested" / "report.txt"
    report = generate_report(_meta(), _df(), output_path=str(out_path))
    assert out_path.exists()
    assert out_path.read_text(encoding="utf-8") == report
