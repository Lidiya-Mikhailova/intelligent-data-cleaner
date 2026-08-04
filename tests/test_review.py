import json

import pandas as pd
import pytest

from src.core.metadata import DocumentMetadata, ProcessingStep
from src.document import Document
from src.dq import DQ_COLUMNS
from src.review import (
    DataQualityMetrics,
    QuarantineRecord,
    ReportSummary,
    _build_quarantine_records,
    _classify_quarantine_reason,
    _count_broken_dates,
    _count_issue_category,
    _count_suspicious_rows,
    _parse_dq_checks_raw,
    build_document_report,
    build_report_summary,
    format_report_txt,
    write_report_files,
)


def _chk(name, status, severity="info", details=None):
    return {
        "check_name": name,
        "category": "test",
        "status": status,
        "severity": severity,
        "message": f"{name} message",
        "details": details or {},
    }


def _checks_json(*issues):
    return json.dumps(list(issues), ensure_ascii=False, separators=(",", ":"))


# Parse helpers


def test_parse_dq_checks_raw_variants():
    assert _parse_dq_checks_raw("") == []
    assert _parse_dq_checks_raw(None) == []
    assert _parse_dq_checks_raw([]) == []
    assert _parse_dq_checks_raw('[{"a": 1}]') == [{"a": 1}]
    assert _parse_dq_checks_raw("[not json") == []
    assert _parse_dq_checks_raw(42) == []
    assert _parse_dq_checks_raw([{"a": 1}]) == [{"a": 1}]


# Classification of quarantine reasons


@pytest.mark.parametrize(
    ("issue", "reason", "category", "confidence"),
    [
        (_chk("ocr_corrupted", "fail", "error"), "OCR corruption detected", "ocr_corruption", 0.7),
        (
            _chk("critical_nulls", "fail", "error", {"field": "Name"}),
            "Missing required field: Name",
            "missing_field",
            0.85,
        ),
        (_chk("suspicious_empty", "fail", "error"), "Record is >80% empty", "sparse_record", 0.6),
        (
            _chk("field_types", "fail", "error", {"field": "Age"}),
            "Type coercion failed for 'Age'",
            "coercion_failure",
            0.8,
        ),
        (_chk("dedup_collision", "fail", "error"), "Exact duplicate detected", "duplicate", 0.95),
        (
            _chk("translation_broken_unicode", "fail", "error"),
            "Broken unicode in field",
            "encoding_issue",
            0.75,
        ),
        (
            _chk("normalization_mojibake", "fail", "error"),
            "Possible mojibake in field",
            "mojibake",
            0.65,
        ),
        (
            _chk("translation_empty", "warn", "warn"),
            "Empty translation",
            "missing_translation",
            0.5,
        ),
    ],
)
def test_classify_quarantine_reason(issue, reason, category, confidence):
    assert _classify_quarantine_reason([issue])[:3] == (reason, category, confidence)


def test_classify_quarantine_reason_unknown():
    assert _classify_quarantine_reason([]) == ("Suspicious record flagged by DQ", "unknown", 0.4, "Review manually")


def test_classify_quarantine_reason_prefers_first_match():
    issues = [_chk("dedup_collision", "fail", "error"), _chk("field_types", "fail", "error", {"field": "Age"})]
    reason, category, _, _ = _classify_quarantine_reason(issues)
    assert reason == "Exact duplicate detected"
    assert category == "duplicate"


# Aggregation helpers


def test_count_issue_category():
    df = pd.DataFrame(
        {
            DQ_COLUMNS[2]: [
                _checks_json(_chk("ocr_corrupted", "fail", "error")),
                _checks_json(_chk("ocr_corrupted", "warn", "warn")),
                _checks_json(_chk("dedup_collision", "fail", "error")),
            ]
        }
    )
    assert _count_issue_category(df, "ocr_corrupted") == 1
    assert _count_issue_category(df, "ocr_corrupted", status="warn") == 1
    assert _count_issue_category(df, "dedup_collision") == 1


def test_count_issue_category_no_column():
    df = pd.DataFrame({"Name": ["a"]})
    assert _count_issue_category(df, "ocr_corrupted") == 0


def test_count_broken_dates():
    df = pd.DataFrame(
        {
            DQ_COLUMNS[2]: [
                _checks_json(_chk("field_types", "fail", "error", {"field": "d", "value": "2023-01-01"})),
                _checks_json(_chk("field_types", "warn", "warn", {"field": "d", "value": "01/02/2024"})),
                _checks_json(_chk("field_types", "fail", "error", {"field": "d", "value": "abc"})),
                _checks_json(_chk("dedup_collision", "fail", "error")),
            ]
        }
    )
    assert _count_broken_dates(df) == 2


def test_count_suspicious_rows():
    q = pd.DataFrame({"ID": [1, 2]})
    inv = pd.DataFrame({"ID": [3]})
    assert _count_suspicious_rows(q, inv) == 3


# Quarantine record building


def _dq_df(rows):
    return pd.DataFrame(rows)


def test_build_quarantine_records_strips_dq_and_uses_overrides():
    q = _dq_df(
        {
            "ID": [1],
            "Name": ["Alice"],
            "quarantine_reasons": ["manual reason"],
            DQ_COLUMNS[2]: [_checks_json(_chk("translation_empty", "warn", "warn"))],
        }
    )
    inv = _dq_df(
        {
            "ID": [2],
            "Name": [""],
            "validation_error": ["Bad record"],
            DQ_COLUMNS[2]: [_checks_json(_chk("field_types", "fail", "error", {"field": "ID"}))],
        }
    )
    records = _build_quarantine_records(q, inv)
    assert len(records) == 2
    qr0, qr1 = records
    assert qr0.row_index == 0
    assert qr0.reason == "manual reason"
    assert qr0.category == "missing_translation"
    assert qr0.data == {"ID": 1, "Name": "Alice", "quarantine_reasons": "manual reason"}
    assert qr1.row_index == 1
    assert qr1.reason == "Bad record"
    assert qr1.category == "coercion_failure"
    assert qr1.data == {"ID": 2, "Name": ""}


def test_build_quarantine_records_without_dq_column():
    q = _dq_df({"ID": [1], "Name": ["Alice"]})
    inv = _dq_df({"ID": [2], "Name": ["Bob"]})
    records = _build_quarantine_records(q, inv)
    assert len(records) == 2
    assert records[0].reason == "Suspicious record flagged by DQ"
    assert records[1].row_index == 1


# Data models


def test_data_quality_metrics_to_dict_rounds_null_rate():
    m = DataQualityMetrics(null_rate=0.123456)
    d = m.to_dict()
    assert d["null_rate"] == 0.1235
    assert d["rows_total"] == 0


def test_data_quality_metrics_merge():
    a = DataQualityMetrics(rows_total=2, null_rate=0.2, schema_drift_detected=False)
    b = DataQualityMetrics(rows_total=3, null_rate=0.1, schema_drift_detected=True)
    merged = a.merge(b)
    assert merged.rows_total == 5
    assert merged.null_rate == 0.2
    assert merged.schema_drift_detected is True


def test_report_summary_coerces_dict_records():
    r = ReportSummary(
        source_file="x.csv",
        pipeline_run_id=1,
        quarantine_records=[
            {"row_index": 0, "data": {}, "reason": "r", "category": "c", "confidence": 0.5}
        ],
    )
    assert isinstance(r.quarantine_records[0], QuarantineRecord)
    assert r.quarantine_records[0].reason == "r"


def test_report_summary_to_dict():
    r = ReportSummary(source_file="x.csv", pipeline_run_id=7, null_rate=0.25, stages=[{"name": "n"}])
    d = r.to_dict()
    assert d["source_file"] == "x.csv"
    assert d["pipeline_run_id"] == 7
    assert d["null_rate"] == 0.25
    assert d["stages"] == [{"name": "n"}]


# build_report_summary


def _summary_inputs():
    quarantine_df = pd.DataFrame(
        {
            "ID": [1],
            "Name": ["Alice"],
            DQ_COLUMNS[2]: [_checks_json(_chk("translation_empty", "warn", "warn"))],
        }
    )
    invalid_df = pd.DataFrame(
        {
            "ID": [2],
            "Name": [""],
            "validation_error": ["Bad"],
            DQ_COLUMNS[2]: [_checks_json(_chk("field_types", "fail", "error", {"field": "d", "value": "2023-01-01"}))],
        }
    )
    valid_df = pd.DataFrame({"ID": [3], "Name": ["Bob"]})
    processed_df = pd.concat([quarantine_df, invalid_df], ignore_index=True)
    raw_df = pd.concat([processed_df, valid_df], ignore_index=True)
    metrics = DataQualityMetrics(
        rows_total=3,
        rows_valid=1,
        rows_invalid=1,
        rows_quarantine=1,
        duplicates_removed=5,
        null_rate=0.25,
        type_conversion_failures=2,
        schema_drift_detected=True,
    )
    return raw_df, processed_df, valid_df, invalid_df, quarantine_df, metrics


def test_build_report_summary_counts():
    raw_df, processed_df, valid_df, invalid_df, quarantine_df, metrics = _summary_inputs()
    report = build_report_summary(
        source_file="mem.csv",
        raw_df=raw_df,
        processed_df=processed_df,
        valid_df=valid_df,
        invalid_df=invalid_df,
        quarantine_df=quarantine_df,
        dq_metrics=metrics,
        stages=[{"name": "normalize"}],
    )
    assert report.rows_total == 3
    assert report.rows_valid == 1
    assert report.rows_invalid == 1
    assert report.rows_quarantine == 1
    assert report.duplicates_detected == 5
    assert report.broken_dates == 1
    assert report.coercion_failures == 2
    assert report.suspicious_rows_count == 2
    assert report.schema_drift_detected is True
    assert report.stages == [{"name": "normalize"}]
    assert len(report.quarantine_records) == 2


# format_report_txt


def test_format_report_txt_with_records():
    summary = ReportSummary(
        source_file="mem.csv",
        pipeline_run_id=0,
        rows_total=10,
        rows_valid=8,
        rows_invalid=1,
        rows_quarantine=1,
        quarantine_records=[
            QuarantineRecord(
                row_index=0,
                data={"ID": 1, "Name": "Alice"},
                reason="Missing required field: Name",
                category="missing_field",
                confidence=0.85,
                suggested_normalization="Fill in 'Name'",
            )
        ],
    )
    txt = format_report_txt(summary)
    assert "DATA QUALITY REPORT" in txt
    assert "Valid records:        8" in txt
    assert "Missing required field: Name" in txt
    assert "Fill in 'Name'" in txt
    assert "Problem Records" in txt


def test_format_report_txt_no_records():
    summary = ReportSummary(source_file="mem.csv", pipeline_run_id=0, rows_total=1, rows_valid=1)
    txt = format_report_txt(summary)
    assert "No problem records found." in txt


# Document integration


def _dq_document():
    df = pd.DataFrame(
        {
            "ID": [1],
            "Name": ["Alice"],
            DQ_COLUMNS[0]: [0.3],
            DQ_COLUMNS[1]: ["warn"],
            DQ_COLUMNS[2]: [_checks_json(_chk("translation_empty", "warn", "warn"))],
        }
    )
    meta = DocumentMetadata(source="mem.csv", source_format="csv")
    meta.add_step(ProcessingStep(name="normalize", rows_before=1, rows_after=1))
    doc = Document(df, metadata=meta)
    return doc


def test_build_document_report():
    report = build_document_report(_dq_document())
    assert report.rows_total == 1
    assert report.rows_quarantine == 1
    assert report.rows_invalid == 0
    assert len(report.stages) == 1
    assert report.stages[0]["name"] == "normalize"
    assert len(report.quarantine_records) == 1


def test_write_report_files(tmp_path):
    review_path, quarantine_path, report = write_report_files(_dq_document(), output_dir=str(tmp_path))
    assert review_path.exists()
    assert quarantine_path.exists()
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    assert payload["rows_total"] == 1
    assert payload["rows_quarantine"] == 1
    assert len(payload["quarantine_records"]) == 1
    assert "DQ:translation_empty" in payload["quarantine_records"][0]["reason"]
    qr_csv = pd.read_csv(quarantine_path)
    assert list(qr_csv.columns) == ["ID", "Name", "quarantine_reasons", "_reason", "_category", "_confidence"]
    assert "DQ:translation_empty" in qr_csv.iloc[0]["_reason"]
