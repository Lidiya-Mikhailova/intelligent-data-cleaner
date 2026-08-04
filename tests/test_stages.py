
import pandas as pd
import pytest

from src.core.exceptions import UnsupportedFormatError
from src.document import Document
from src.normalization.base import ProcessingStage
from src.normalization.pipeline import Pipeline
from src.normalization.stages import (
    CleanStage,
    DeduplicateStage,
    EnrichStage,
    ExportStage,
    ExtractStage,
    FormDetectStage,
    IngestStage,
    NormalizeStage,
    TranslateStage,
)


def _doc(df=None):
    return Document(pd.DataFrame() if df is None else df)


# IngestStage — from file


def test_ingest_from_csv_file(tmp_path):
    path = tmp_path / "in.csv"
    path.write_text("Name,Age\nAlice,30\nBob,25\n", encoding="utf-8")
    doc = Pipeline([IngestStage(path=path)]).run(_doc())
    assert doc.shape == (2, 2)
    assert doc.metadata.source_format == "csv"
    assert doc.metadata.processing_stages == ["ingest"]


def test_ingest_unsupported_format(tmp_path):
    path = tmp_path / "in.unknown"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        IngestStage(path=path).process(_doc())


def test_ingest_missing_file_raises(tmp_path):
    with pytest.raises(Exception):
        IngestStage(path=tmp_path / "nope.csv").process(_doc())


# IngestStage — from text


def test_ingest_text_csv():
    doc = IngestStage(source="text", data="Name,Age\nAlice,30\nBob,25").process(_doc())
    assert doc.shape == (2, 2)
    assert doc.metadata.source_format == "csv"


def test_ingest_text_kv():
    doc = IngestStage(source="text", data="Name: Alice\nAge: 30\nCity = Paris").process(_doc())
    assert "Field" in doc.columns
    assert "Value" in doc.columns
    assert doc.metadata.source_format == "txt"


# IngestStage — from dict


def test_ingest_single_dict():
    doc = IngestStage(source="dict", data={"Name": "Alice", "Age": 30}).process(_doc())
    assert doc.shape == (1, 2)
    assert doc.data.iloc[0]["Age"] == "30"


def test_ingest_list_of_dicts():
    doc = IngestStage(source="dict", data=[{"A": 1}, {"A": 2}, {"A": 3}]).process(_doc())
    assert doc.shape == (3, 1)


def test_ingest_dict_invalid_data():
    with pytest.raises(ValueError):
        IngestStage(source="dict", data="nope").process(_doc())


# IngestStage — from bytes


@pytest.mark.parametrize(
    ("fmt", "payload", "expected_col"),
    [
        ("csv", b"Name,Age\nAlice,30\n", "Name"),
        ("json", b'[{"A": 1}]', "A"),
        ("jsonl", b'{"A": 1}\n{"A": 2}\n', "A"),
        ("txt", b"Name: Alice\nAge: 30\n", "Field"),
    ],
)
def test_ingest_bytes_formats(fmt, payload, expected_col):
    doc = IngestStage(source="bytes", data=payload, format=fmt).process(_doc())
    assert expected_col in doc.columns


def test_ingest_bytes_unsupported():
    with pytest.raises(UnsupportedFormatError):
        IngestStage(source="bytes", data=b"x", format="docx").process(_doc())


def test_ingest_no_source_passthrough():
    doc = _doc(pd.DataFrame({"A": [1]}))
    result = IngestStage().process(doc)
    assert result.shape == (1, 1)


# FormDetectStage


def test_form_detect_skips_empty():
    doc = _doc()
    result = FormDetectStage().process(doc)
    assert result.is_empty


def test_form_detect_returns_unchanged_when_no_form():
    df = pd.DataFrame({"Text": ["Just some random data"]})
    result = FormDetectStage().process(_doc(df))
    assert result.shape == (1, 1)


def test_form_detect_field_value_source_line():
    df = pd.DataFrame({"Field": ["Filing Status"], "Value": ["Single"], "SourceLine": ["Filing Status: Single"]})
    doc = _doc(df)
    result = FormDetectStage().process(doc)
    assert "Field" in result.columns


def test_form_detect_runs_extraction():
    df = pd.DataFrame({"Field": ["Text"], "Value": ["Form 1099-NEC"], "SourceLine": ["Form 1099-NEC"]})
    doc = _doc(df)
    result = FormDetectStage().process(doc)
    assert "Field" in result.columns
    assert "form_detect" in result.metadata.processing_stages


def test_form_detect_empty_source_lines():
    df = pd.DataFrame({"A": [None, None]})
    result = FormDetectStage().process(_doc(df))
    assert result.shape == (2, 1)


def test_form_detect_extraction_empty(monkeypatch):
    import src.forms as forms

    monkeypatch.setattr(forms, "detect_form", lambda lines: "1099")
    monkeypatch.setattr(forms, "extract_form", lambda lines, form_type: pd.DataFrame())
    df = pd.DataFrame({"Text": ["Form 1099-NEC", "x"]})
    result = FormDetectStage().process(_doc(df))
    assert result.shape == (2, 1)


# ExtractStage


def test_extract_kv_from_single_column():
    df = pd.DataFrame({"text": ["Name: Alice", "Age: 30", "City: Paris"]})
    doc = _doc(df)
    result = ExtractStage().process(doc)
    assert "Field" in result.columns
    assert "Value" in result.columns


def test_extract_no_kv_unchanged():
    df = pd.DataFrame({"text": ["hello", "world", "foo"]})
    result = ExtractStage().process(_doc(df))
    assert result.shape == (3, 1)


def test_extract_multiple_columns_unchanged():
    df = pd.DataFrame({"A": [1], "B": [2]})
    result = ExtractStage().process(_doc(df))
    assert result.shape == (1, 2)


# NormalizeStage


def test_normalize_stage_cleans_text():
    df = pd.DataFrame({"Name": ["  Alice  ", "Bob  ", "Carol"]})
    result = NormalizeStage().process(_doc(df))
    assert "  " not in str(result.data["Name"].iloc[0])
    assert "normalize" in result.metadata.processing_stages


def test_normalize_stage_params_recorded():
    df = pd.DataFrame({"A": ["x"]})
    result = NormalizeStage(fix_encoding=False, normalize_whitespace=False).process(_doc(df))
    step = [s for s in result.metadata.processing_history if s.name == "normalize"][0]
    assert step.params == {"fix_encoding": False, "normalize_whitespace": False}


# CleanStage


def test_clean_stage_adds_metrics():
    df = pd.DataFrame({"A": ["1", "2", "3"]})
    result = CleanStage().process(_doc(df))
    assert "type_conversion_failures" in result.metadata.quality_metrics
    assert "clean" in result.metadata.processing_stages


def test_clean_stage_structural_only_flag():
    df = pd.DataFrame({"A": ["x", "y"]})
    result = CleanStage(structural_only=True).process(_doc(df))
    assert result.shape[0] >= 1


# DeduplicateStage


def test_deduplicate_exact_removes_dupes():
    df = pd.DataFrame({"Name": ["Alice", "alice ", "Bob"], "Age": [30, 30, 25]})
    doc = _doc(df)
    result = DeduplicateStage().process(doc)
    assert len(result) == 2
    assert len(result.duplicates) == 1


def test_deduplicate_subset():
    df = pd.DataFrame({"Name": ["Alice", "Alice", "Bob"], "Age": [30, 31, 25]})
    result = DeduplicateStage(subset=["Name"]).process(_doc(df))
    assert len(result) == 2


def test_deduplicate_fuzzy():
    df = pd.DataFrame({"Name": ["Acme Corporation", "ACME Corporation", "Bob"]})
    result = DeduplicateStage(threshold=80.0, fuzzy=True).process(_doc(df))
    assert len(result) == 2


# TranslateStage


def test_translate_stage_calls_engine(monkeypatch):
    from src.translation import engine

    def fake_translate_dataframe(df, target="en", source=None, columns=None):
        return df

    monkeypatch.setattr(engine, "translate_dataframe", fake_translate_dataframe)
    df = pd.DataFrame({"A": ["hello"]})
    result = TranslateStage(target="en").process(_doc(df))
    assert "translate" in result.metadata.processing_stages


# EnrichStage


def test_enrich_adds_missing_columns():
    df = pd.DataFrame({"A": [1]})
    result = EnrichStage(rules={"source": "internal", "country": "US"}).process(_doc(df))
    assert result.data["source"].tolist() == ["internal"]
    assert result.data["country"].tolist() == ["US"]


def test_enrich_keeps_existing_columns():
    df = pd.DataFrame({"A": [1], "source": ["x"]})
    result = EnrichStage(rules={"source": "internal"}).process(_doc(df))
    assert result.data["source"].tolist() == ["x"]


def test_enrich_no_rules():
    df = pd.DataFrame({"A": [1]})
    result = EnrichStage().process(_doc(df))
    assert result.shape == (1, 1)


# ExportStage


def test_export_stage_no_format_skips(tmp_path):
    df = pd.DataFrame({"A": [1]})
    result = ExportStage().process(_doc(df))
    assert result.shape == (1, 1)


def test_export_stage_with_format_writes(tmp_path):
    df = pd.DataFrame({"A": [1, 2]})
    out = tmp_path / "out.csv"
    ExportStage(fmt="csv", output_path=str(out)).process(_doc(df))
    assert out.exists()


# ProcessingStage base


def test_stage_repr():
    class MyStage(ProcessingStage):
        name = "my"

        def process(self, doc):
            return doc

    assert repr(MyStage()) == "<Stage: my>"
