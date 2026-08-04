import json

import pandas as pd

from src.dq import (
    DQ_COLUMNS,
    DQService,
    _score_from_results,
    _status_from_score,
    check_dedup_quality,
    check_normalization_quality,
    check_nulls,
    check_ocr_quality,
    check_schema,
    check_translation_quality,
    check_types,
)


def _non_pass(checks_json: str) -> list:
    return [c for c in json.loads(checks_json) if c["status"] != "pass"]


# check_schema


def test_schema_pass():
    df = pd.DataFrame({"ID": [1], "Name": ["Alice"]})
    result = check_schema(df, required_fields=["ID", "Name"])
    assert all(len(r) == 1 and r[0]["status"] == "pass" for r in result)


def test_schema_missing_required():
    df = pd.DataFrame({"ID": [1], "Name": [""]})
    result = check_schema(df, required_fields=["ID", "Name"])
    fails = [r for r in result.iloc[0] if r["status"] == "fail"]
    assert any("Name" in f["message"] for f in fails)


def test_schema_no_required():
    df = pd.DataFrame({"ID": [1], "Name": ["Alice"]})
    result = check_schema(df)
    assert all(len(r) == 1 and r[0]["status"] == "pass" for r in result)


# check_types


def test_types_pass():
    df = pd.DataFrame({"ID": [1], "Age": [30]})
    result = check_types(df, numeric_fields=["ID", "Age"])
    assert all(r[0]["status"] == "pass" for r in result)


def test_types_invalid_number():
    df = pd.DataFrame({"Age": ["abc"]})
    result = check_types(df, numeric_fields=["Age"])
    assert result.iloc[0][0]["status"] == "warn"


def test_types_date_pass():
    df = pd.DataFrame({"Date": ["2024-01-15"]})
    result = check_types(df, date_fields=["Date"])
    assert result.iloc[0][0]["status"] == "pass"


# check_nulls


def test_nulls_pass():
    df = pd.DataFrame({"ID": [1], "Name": ["Alice"]})
    result = check_nulls(df, critical_fields=["ID", "Name"])
    assert all(r[0]["status"] == "pass" for r in result)


def test_nulls_critical_field_empty():
    df = pd.DataFrame({"Name": [""]})
    result = check_nulls(df, critical_fields=["Name"])
    assert result.iloc[0][0]["status"] == "fail"


def test_nulls_suspicious_empty():
    df = pd.DataFrame({"a": [""], "b": [""], "c": [""], "d": [""]})
    result = check_nulls(df)
    assert any(r["check_name"] == "suspicious_empty" and r["status"] == "warn" for r in result.iloc[0])


# check_ocr_quality


def test_ocr_quality_pass():
    df = pd.DataFrame({"Text": ["Hello world"]})
    result = check_ocr_quality(df)
    assert all(r[0]["status"] == "pass" for r in result)


def test_ocr_garbage_chars():
    df = pd.DataFrame({"Text": ["hello $%^ world"]})
    result = check_ocr_quality(df)
    fails = [r for r in result.iloc[0] if r["status"] == "fail"]
    assert any("corrupted" in f["check_name"] for f in fails)


def test_ocr_high_noise():
    df = pd.DataFrame({"Text": ["!!!###$$$^^^"]})
    result = check_ocr_quality(df)
    warns = [r for r in result.iloc[0] if r["status"] == "warn"]
    assert any("noise" in w["check_name"] for w in warns)


# check_dedup_quality


def test_dedup_quality_pass():
    df = pd.DataFrame({"Name": ["Alice", "Bob"]})
    result = check_dedup_quality(df)
    assert all(r[0]["status"] == "pass" for r in result)


def test_dedup_quality_finds_duplicate():
    df = pd.DataFrame({"Name": ["Alice", "Alice"]})
    result = check_dedup_quality(df)
    fails = [r for r in result.iloc[1] if r["status"] == "warn"]
    assert any("collision" in f["check_name"] for f in fails)


# check_translation_quality


def test_translation_pass():
    df = pd.DataFrame({"Text": ["hello"]})
    result = check_translation_quality(df)
    assert all(r[0]["status"] == "pass" for r in result)


def test_translation_broken_unicode():
    df = pd.DataFrame({"Text": ["hello\ufffdworld"]})
    result = check_translation_quality(df)
    fails = [r for r in result.iloc[0] if r["status"] == "fail"]
    assert any("broken_unicode" in f["check_name"] for f in fails)


# check_normalization_quality


def test_normalization_pass():
    df = pd.DataFrame({"Text": ["normal text"]})
    result = check_normalization_quality(df)
    assert all(r[0]["status"] == "pass" for r in result)


def test_normalization_control_chars():
    df = pd.DataFrame({"Text": ["hello\x00world"]})
    result = check_normalization_quality(df)
    warns = [r for r in result.iloc[0] if r["status"] == "warn"]
    assert any("control_chars" in w["check_name"] for w in warns)


# _score_from_results / _status_from_score


def test_score_pass():
    assert _score_from_results([]) == 0.0
    assert _score_from_results([{"status": "pass", "severity": "info"}]) == 0.0


def test_score_warn():
    score = _score_from_results([{"status": "warn", "severity": "warn"}])
    assert 0.2 <= score <= 0.4


def test_score_fail():
    score = _score_from_results([{"status": "fail", "severity": "error"}])
    assert score >= 0.6


def test_status_from_score():
    assert _status_from_score(0.0) == "pass"
    assert _status_from_score(0.3) == "warn"
    assert _status_from_score(0.6) == "fail"


# DQService


def test_dq_service_adds_columns():
    df = pd.DataFrame({"ID": [1], "Name": ["Alice"]})
    result = DQService().run_all(df.copy())
    for col in DQ_COLUMNS:
        assert col in result.columns


def test_dq_service_passthrough_empty():
    result = DQService().run_all(pd.DataFrame())
    assert result.empty


def test_dq_service_handles_existing_dq_cols():
    df = pd.DataFrame({"ID": [1], "_dq_score": [0.5], "_dq_status": ["old"], "_dq_checks": ["[]"]})
    result = DQService().run_all(df.copy())
    assert result["_dq_score"].iloc[0] == 0.0
    assert result["_dq_status"].iloc[0] == "pass"


def test_dq_service_flags_issues(tmp_path):
    df = pd.DataFrame(
        {
            "ID": [1, 2],
            "Name": ["Alice", "Bob"],
            "Notes": ["ok", "hello\ufffdworld"],
        }
    )
    result = DQService().run_all(df)
    assert result.iloc[0]["_dq_status"] == "pass"
    assert result.iloc[1]["_dq_status"] == "fail"


# quality_report


def test_quality_report_empty():
    report = DQService().quality_report(pd.DataFrame())
    assert report["status"] == "no_data"


def test_quality_report_with_dq():
    df = pd.DataFrame(
        {
            "ID": [1, 2],
            "Name": ["Alice", "Bob"],
            "Notes": ["ok", "hello\ufffdworld"],
        }
    )
    result = DQService().run_all(df)
    report = DQService().quality_report(result)
    assert report["total"] == 2
    assert "avg_dq_score" in report
    assert "dq_status_counts" in report
    assert "pass_rate" in report


def test_quality_report_with_dq_only():
    df = DQService().run_all(pd.DataFrame({"x": ["a"], "y": ["b"]}))
    report = DQService().quality_report(df)
    assert report["total"] == 1
    assert report["pass_rate"] == 1.0


# Integration: classify_records with DQ


def test_classify_with_dq_pass():
    from src.core.validation import classify_records

    df = pd.DataFrame(
        {
            "ID": [1],
            "Name": ["Alice"],
            "Age": [30],
            "Email": ["alice@example.com"],
            "Address": ["123 Main St"],
            "Notes": ["OK"],
        }
    )
    dq_df = DQService().run_all(df)
    valid, invalid, quarantine = classify_records(dq_df)
    assert len(valid) == 1
    assert len(invalid) == 0
    assert len(quarantine) == 0


def test_classify_with_dq_critical():
    from src.core.validation import classify_records

    df = pd.DataFrame(
        {
            "ID": [1],
            "Name": ["Alice"],
            "Age": [30],
            "Email": ["alice@example.com"],
            "Notes": ["hello\ufffdworld"],
        }
    )
    dq_df = DQService().run_all(df)
    valid, invalid, quarantine = classify_records(dq_df)
    assert len(invalid) >= 1


def test_classify_with_dq_warn():
    from src.core.validation import classify_records

    df = pd.DataFrame(
        {
            "ID": [1],
            "Name": ["Alice"],
            "Age": [30],
            "Email": ["alice@example.com"],
            "Notes": ["hello\x00world"],
        }
    )
    dq_df = DQService().run_all(df)
    valid, invalid, quarantine = classify_records(dq_df)
    assert len(quarantine) >= 1


# Integration: Document API


def test_document_validate():
    from src.document import Document

    doc = Document.from_dict({"ID": 1, "Name": "Alice", "Age": 30, "Email": "alice@example.com"})
    doc.validate()
    assert "_dq_score" in doc.data.columns
    assert doc.data.iloc[0]["_dq_status"] == "pass"


def test_document_quality_report():
    from src.document import Document

    doc = Document.from_dict({"ID": 1, "Name": "Alice", "Age": 30, "Email": "alice@example.com"})
    report = doc.quality_report()
    assert isinstance(report, dict)
    assert "total" in report
    if report["status"] != "no_data":
        assert report["total"] >= 1


# DQStage


def test_dq_stage():
    from src.dq import DQStage

    stage = DQStage()
    assert stage.name == "dq"
    from src.document import Document

    doc = Document.from_dict({"ID": 1, "Name": "Alice"})
    result = stage.process(doc)
    for col in DQ_COLUMNS:
        assert col in result.data.columns
