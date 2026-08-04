import pandas as pd
import pytest

from src.document import Document


def _doc(df=None):
    return Document(pd.DataFrame() if df is None else df)


# Properties


def test_review_getter_setter():
    doc = _doc(pd.DataFrame({"A": [1]}))
    assert doc.review is None
    doc.review = "summary"
    assert doc.review == "summary"


def test_quarantine_property_returns_copy():
    doc = _doc(pd.DataFrame({"A": [1]}))
    q = doc.quarantine
    assert q.empty
    q["A"] = [99]
    assert doc.quarantine.empty


# Factory methods


def test_from_file(tmp_path):
    path = tmp_path / "d.csv"
    path.write_text("Name,Age\nAlice,30\n", encoding="utf-8")
    doc = Document.from_file(path)
    assert doc.shape == (1, 2)
    assert "ingest" in doc.metadata.processing_stages


def test_from_file_missing_raises():
    with pytest.raises(FileNotFoundError):
        Document.from_file("does-not-exist.csv")


def test_from_text_kv():
    doc = Document.from_text("Name: Alice\nAge: 30")
    assert "Field" in doc.columns
    assert "Value" in doc.columns


def test_from_dict_single():
    doc = Document.from_dict({"Name": "Alice", "Age": 30})
    assert doc.shape == (1, 2)


def test_from_dict_list():
    doc = Document.from_dict([{"A": 1}, {"A": 2}])
    assert doc.shape == (2, 1)


def test_from_bytes_csv():
    doc = Document.from_bytes(b"Name,Age\nAlice,30\n", format="csv")
    assert doc.shape == (1, 2)
    assert doc.data.iloc[0]["Age"] == "30"


def test_classify_sets_review_and_quarantine():
    doc = _doc(pd.DataFrame({"Name": ["Alice", "Bob"]}))
    valid, invalid, quarantine = doc.classify(strict=True)
    assert isinstance(valid, pd.DataFrame)
    assert isinstance(invalid, pd.DataFrame)
    assert isinstance(quarantine, pd.DataFrame)
    assert doc.review is not None
    assert doc.review.rows_total == 2


# find_duplicates


def test_find_duplicates_empty():
    doc = _doc()
    assert doc.find_duplicates().empty


def test_find_duplicates_fuzzy():
    df = pd.DataFrame({"Name": ["Alice", "alice ", "Bob"]})
    result = _doc(df).find_duplicates(fuzzy=True, threshold=80.0)
    assert len(result) >= 1


def test_find_duplicates_exact():
    df = pd.DataFrame({"Name": ["Alice", "alice ", "Bob"]})
    result = _doc(df).find_duplicates(fuzzy=False)
    assert len(result) == 2


def test_find_duplicates_subset():
    df = pd.DataFrame({"Name": ["Alice", "Alice"], "Age": [30, 31]})
    result = _doc(df).find_duplicates(fuzzy=False, subset=["Name"])
    assert len(result) == 2


def test_suspicious_no_dq_column():
    doc = _doc(pd.DataFrame({"A": [1]}))
    assert doc.suspicious().empty


def test_suspicious_with_dq_column():
    df = pd.DataFrame({"A": [1, 2, 3], "_dq_status": ["pass", "warn", "fail"]})
    result = _doc(df).suspicious()
    assert len(result) == 2


# Row operations


def test_remove_rows_list():
    doc = _doc(pd.DataFrame({"A": [1, 2, 3]}))
    result = doc.remove_rows([0, 2])
    assert result.data["A"].tolist() == [2]


def test_remove_rows_int():
    doc = _doc(pd.DataFrame({"A": [1, 2, 3]}))
    result = doc.remove_rows(1)
    assert result.data["A"].tolist() == [1, 3]


def test_remove_rows_out_of_range():
    doc = _doc(pd.DataFrame({"A": [1, 2, 3]}))
    result = doc.remove_rows([99, -5])
    assert result.shape == (3, 1)


def test_keep_rows():
    doc = _doc(pd.DataFrame({"A": [1, 2, 3, 4]}))
    result = doc.keep_rows(lambda row: row["A"] % 2 == 0)
    assert result.data["A"].tolist() == [2, 4]


# transform


def test_transform_type_error():
    doc = _doc(pd.DataFrame({"A": [1]}))
    with pytest.raises(TypeError):
        doc.transform(lambda df: "not a dataframe", "bad")


def test_transform_records_step():
    doc = _doc(pd.DataFrame({"A": [1]}))
    doc.transform(lambda df: df.assign(B=2), "custom")
    assert doc.metadata.processing_stages[-1] == "custom"


# Convenience methods


def test_normalize_and_clean_convenience():
    df = pd.DataFrame({"Name": ["  Alice  "], "Age": ["30"]})
    doc = _doc(df).normalize().clean()
    assert "normalize" in doc.metadata.processing_stages
    assert "clean" in doc.metadata.processing_stages


def test_deduplicate_convenience():
    df = pd.DataFrame({"Name": ["Alice", "alice "]})
    doc = _doc(df).deduplicate()
    assert len(doc) == 1
    assert len(doc.duplicates) == 1


def test_enrich_convenience():
    doc = _doc(pd.DataFrame({"A": [1]})).enrich(source="x")
    assert doc.data["source"].tolist() == ["x"]


def test_validate_convenience():
    doc = _doc(pd.DataFrame({"A": [1, 2, 3]})).validate()
    assert "_dq_status" in doc.data.columns


def test_quality_report():
    doc = _doc(pd.DataFrame({"A": [1, 2]}))
    report = doc.quality_report()
    assert isinstance(report, dict)
    assert doc.quality_metrics == {}


def test_run_pipeline_none_uses_full():
    doc = _doc(pd.DataFrame({"Name": ["Alice", "Bob"]}))
    result = doc.run_pipeline()
    assert len(result.metadata.processing_history) >= 1


def test_run_pipeline_custom_stages():
    doc = _doc(pd.DataFrame({"A": [1]}))
    result = doc.run_pipeline(["enrich", "clean"])
    assert result.metadata.processing_stages == ["enrich", "clean"]


# Terminal operations


def test_report_and_diff_and_views():
    doc = _doc(pd.DataFrame({"A": [1, 2]}))
    other = _doc(pd.DataFrame({"A": [2, 3]}))
    assert "Document" in doc.report() or len(doc.report()) > 0
    assert isinstance(doc.diff(other), str)
    assert len(doc.head(1)) == 1
    assert doc.to_pandas().shape == (2, 1)


def test_repr_and_len():
    doc = _doc(pd.DataFrame({"A": [1, 2, 3]}))
    assert len(doc) == 3
    assert "rows=3" in repr(doc)


# Remaining infra properties


def test_is_empty():
    assert _doc().is_empty
    assert not _doc(pd.DataFrame({"A": [1]})).is_empty


def test_removed_property():
    doc = _doc(pd.DataFrame({"Name": ["Alice", "alice "]}))
    doc.deduplicate()
    assert "deduplicate" in doc.removed


def test_find_duplicates_without_rapidfuzz(monkeypatch):
    import importlib.util

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    df = pd.DataFrame({"Name": ["Alice", "alice ", "Bob"]})
    result = _doc(df).find_duplicates(fuzzy=True)
    assert len(result) == 2


def test_translate_convenience(monkeypatch):
    from src.translation import engine
    from src.translation.engine import NullTranslationEngine

    monkeypatch.setattr(engine, "get_translation_engine", lambda *a, **k: NullTranslationEngine())
    df = pd.DataFrame({"A": ["hello"]})
    doc = _doc(df).translate(target="en")
    assert doc.data["A"].tolist() == ["hello"]


def test_quality_report_with_metrics():
    doc = _doc(pd.DataFrame({"A": ["1", "2", "3"]})).clean()
    report = doc.quality_report()
    assert "quality_metrics" in report


def test_setup_logging(tmp_path):
    Document.setup_logging(tmp_path)
    assert (tmp_path / "logs").exists()


def test_list_exporters():
    exporters = Document.list_exporters()
    assert isinstance(exporters, list)
    assert len(exporters) > 0


def test_export_csv_to_path(tmp_path):
    doc = _doc(pd.DataFrame({"A": [1, 2]}))
    out = tmp_path / "o.csv"
    result = doc.export("csv", output_path=str(out))
    assert result == out
    assert out.exists()


def test_export_json_to_bytes():
    doc = _doc(pd.DataFrame({"A": [1, 2]}))
    result = doc.export("json")
    assert isinstance(result, bytes)
    assert b"A" in result


def test_preview():
    doc = _doc(pd.DataFrame({"A": [1, 2]}))
    out = doc.preview(rows=1, show_meta=False)
    assert isinstance(out, str)
    assert "A" in out


def test_preview_with_meta():
    doc = _doc(pd.DataFrame({"A": [1, 2]}))
    out = doc.preview(rows=1)
    assert isinstance(out, str)
    assert "Document" in out or "source" in out.lower()
