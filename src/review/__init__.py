from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.dq import DQ_COLUMNS

logger = logging.getLogger(__name__)


# ── Data Models ───────────────────────────────────────────────────────────────


@dataclass
class DataQualityMetrics:
    rows_total: int = 0
    rows_valid: int = 0
    rows_invalid: int = 0
    rows_quarantine: int = 0
    duplicates_removed: int = 0
    null_rate: float = 0.0
    type_conversion_failures: int = 0
    schema_drift_detected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rows_total": self.rows_total,
            "rows_valid": self.rows_valid,
            "rows_invalid": self.rows_invalid,
            "rows_quarantine": self.rows_quarantine,
            "duplicates_removed": self.duplicates_removed,
            "null_rate": round(self.null_rate, 4),
            "type_conversion_failures": self.type_conversion_failures,
            "schema_drift_detected": self.schema_drift_detected,
        }

    def merge(self, other: DataQualityMetrics) -> DataQualityMetrics:
        return DataQualityMetrics(
            rows_total=self.rows_total + other.rows_total,
            rows_valid=self.rows_valid + other.rows_valid,
            rows_invalid=self.rows_invalid + other.rows_invalid,
            rows_quarantine=self.rows_quarantine + other.rows_quarantine,
            duplicates_removed=self.duplicates_removed + other.duplicates_removed,
            null_rate=max(self.null_rate, other.null_rate),
            type_conversion_failures=self.type_conversion_failures + other.type_conversion_failures,
            schema_drift_detected=self.schema_drift_detected or other.schema_drift_detected,
        )


@dataclass
class QuarantineRecord:
    row_index: int
    data: Dict[str, Any]
    reason: str
    category: str
    confidence: float
    suggested_normalization: Optional[str] = None


@dataclass
class ReportSummary:
    source_file: str
    pipeline_run_id: int
    rows_total: int = 0
    rows_valid: int = 0
    rows_invalid: int = 0
    rows_quarantine: int = 0
    duplicates_detected: int = 0
    possible_ocr_corruption: int = 0
    null_rate: float = 0.0
    coercion_failures: int = 0
    broken_dates: int = 0
    schema_drift_detected: bool = False
    suspicious_rows_count: int = 0
    stages: List[Dict[str, Any]] = field(default_factory=list)
    quarantine_records: List[QuarantineRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "pipeline_run_id": self.pipeline_run_id,
            "rows_total": self.rows_total,
            "rows_valid": self.rows_valid,
            "rows_invalid": self.rows_invalid,
            "rows_quarantine": self.rows_quarantine,
            "duplicates_detected": self.duplicates_detected,
            "possible_ocr_corruption": self.possible_ocr_corruption,
            "null_rate": round(self.null_rate, 4),
            "coercion_failures": self.coercion_failures,
            "broken_dates": self.broken_dates,
            "schema_drift_detected": self.schema_drift_detected,
            "suspicious_rows_count": self.suspicious_rows_count,
            "stages": self.stages,
        }


# ── Helpers ──────────────────────────────────────────────────────────────────


def _extract_dq_issues(row: dict) -> list[dict]:
    raw = row.get(DQ_COLUMNS[2])
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    if isinstance(raw, list):
        return raw
    return []


def _classify_quarantine_reason(issues: list[dict]) -> tuple[str, str, float, Optional[str]]:
    for issue in issues:
        name = issue.get("check_name", "")
        status = issue.get("status", "")
        if status == "fail" and name == "ocr_corrupted":
            return ("OCR corruption detected", "ocr_corruption", 0.7, "Review manually or re-OCR source")
        if name == "critical_nulls":
            field = issue.get("details", {}).get("field", "unknown")
            return (f"Missing required field: {field}", "missing_field", 0.85, f"Fill in '{field}' or mark as optional")
        if name == "suspicious_empty":
            return ("Record is >80% empty", "sparse_record", 0.6, "Remove or fill missing fields")
        if status in ("fail", "warn") and name == "field_types":
            field = issue.get("details", {}).get("field", "unknown")
            return (f"Type coercion failed for '{field}'", "coercion_failure", 0.8, f"Check '{field}' format")
        if name == "dedup_collision":
            return ("Exact duplicate detected", "duplicate", 0.95, "Remove duplicate row")
        if name == "translation_broken_unicode":
            return ("Broken unicode in field", "encoding_issue", 0.75, "Re-encode source text")
        if name == "normalization_mojibake":
            return ("Possible mojibake in field", "mojibake", 0.65, "Re-encode or fix charset")
        if status == "warn" and name == "translation_empty":
            return ("Empty translation", "missing_translation", 0.5, "Re-translate or fill manually")
    return ("Suspicious record flagged by DQ", "unknown", 0.4, "Review manually")


def _count_issue_category(processed_df: pd.DataFrame, check_name: str, status: str = "fail") -> int:
    count = 0
    for _, row in processed_df.iterrows():
        issues = _extract_dq_issues(row.to_dict())
        for issue in issues:
            if issue.get("check_name") == check_name and issue.get("status") == status:
                count += 1
                break
    return count


def _count_broken_dates(processed_df: pd.DataFrame) -> int:
    count = 0
    for _, row in processed_df.iterrows():
        issues = _extract_dq_issues(row.to_dict())
        for issue in issues:
            if issue.get("check_name") == "field_types" and issue.get("status") in ("fail", "warn"):
                details = issue.get("details", {})
                val = str(details.get("value", ""))
                if any(kw in val.lower() for kw in ("date", "/", "-")):
                    count += 1
                    break
    return count


def _count_suspicious_rows(quarantine_df: pd.DataFrame, invalid_df: pd.DataFrame) -> int:
    return len(quarantine_df) + len(invalid_df)


# ── Build Report ─────────────────────────────────────────────────────────────


def build_report_summary(
    source_file: str,
    raw_df: pd.DataFrame,
    processed_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    invalid_df: pd.DataFrame,
    quarantine_df: pd.DataFrame,
    dq_metrics: DataQualityMetrics,
    stages: list[dict],
) -> ReportSummary:
    quarantine_records: List[QuarantineRecord] = []
    for idx, (_, row) in enumerate(quarantine_df.iterrows()):
        row_dict = row.to_dict()
        issues = _extract_dq_issues(row_dict)
        reason, category, confidence, suggestion = _classify_quarantine_reason(issues)
        reasons_raw = row_dict.get("quarantine_reasons", "")
        if reasons_raw:
            reason = reasons_raw
        quarantine_records.append(
            QuarantineRecord(
                row_index=idx,
                data={k: v for k, v in row_dict.items() if k not in DQ_COLUMNS},
                reason=reason,
                category=category,
                confidence=confidence,
                suggested_normalization=suggestion,
            )
        )
    for idx, (_, row) in enumerate(invalid_df.iterrows()):
        row_dict = row.to_dict()
        issues = _extract_dq_issues(row_dict)
        reason, category, confidence, suggestion = _classify_quarantine_reason(issues)
        err = row_dict.get("validation_error", "")
        if err:
            reason = err[:200]
        quarantine_records.append(
            QuarantineRecord(
                row_index=len(quarantine_df) + idx,
                data={k: v for k, v in row_dict.items() if k not in DQ_COLUMNS and k != "validation_error"},
                reason=reason,
                category=category,
                confidence=confidence,
                suggested_normalization=suggestion,
            )
        )
    return ReportSummary(
        source_file=source_file,
        pipeline_run_id=0,
        rows_total=len(raw_df),
        rows_valid=len(valid_df),
        rows_invalid=len(invalid_df),
        rows_quarantine=len(quarantine_df),
        duplicates_detected=dq_metrics.duplicates_removed,
        possible_ocr_corruption=_count_issue_category(processed_df, "ocr_corrupted"),
        null_rate=dq_metrics.null_rate,
        coercion_failures=dq_metrics.type_conversion_failures,
        broken_dates=_count_broken_dates(processed_df),
        schema_drift_detected=dq_metrics.schema_drift_detected,
        suspicious_rows_count=_count_suspicious_rows(quarantine_df, invalid_df),
        stages=stages,
        quarantine_records=quarantine_records,
    )


# ── Format Report ────────────────────────────────────────────────────────────


def format_report_txt(summary: ReportSummary) -> str:
    sb: list[str] = []
    sb.append("=" * 64)
    sb.append(f"  DATA QUALITY REPORT \u2014 {Path(summary.source_file).name}")
    sb.append("=" * 64)
    sb.append("")
    sb.append(f"  Source file:          {summary.source_file}")
    sb.append(f"  Pipeline run ID:      {summary.pipeline_run_id}")
    sb.append("")
    sb.append("  \u2500\u2500 Overview \u2500\u2500")
    sb.append(f"  Total records:        {summary.rows_total}")
    sb.append(f"  Valid records:        {summary.rows_valid}")
    sb.append(f"  Invalid records:      {summary.rows_invalid}")
    sb.append(f"  Quarantine records:   {summary.rows_quarantine}")
    sb.append(f"  Duplicates detected:  {summary.duplicates_detected}")
    sb.append("")
    sb.append("  \u2500\u2500 Data Quality \u2500\u2500")
    sb.append(f"  Null rate:            {summary.null_rate:.2%}")
    sb.append(f"  Type coercion fails:  {summary.coercion_failures}")
    sb.append(f"  Broken dates:         {summary.broken_dates}")
    sb.append(f"  OCR corruption:       {summary.possible_ocr_corruption}")
    sb.append(f"  Schema drift:         {'Yes' if summary.schema_drift_detected else 'No'}")
    sb.append(f"  Suspicious rows:      {summary.suspicious_rows_count}")
    total_pct = summary.rows_valid / max(summary.rows_total, 1)
    sb.append(f"  Valid ratio:          {total_pct:.1%}")
    sb.append("")
    if summary.stages:
        sb.append("  \u2500\u2500 Pipeline Stages \u2500\u2500")
        for s in summary.stages:
            name = s.get("name", "?")
            before = s.get("rows_before", "?")
            after = s.get("rows_after", "?")
            st = s.get("status", "ok")
            sb.append(f"  {name:>16s}  {before} \u2192 {after}  [{st}]")
        sb.append("")
    if summary.quarantine_records:
        sb.append("  \u2500\u2500 Problem Records \u2500\u2500")
        sb.append("")
        for qr in summary.quarantine_records:
            row_preview = ", ".join(
                str(v) for v in list(qr.data.values())[:3] if v is not None and str(v) not in ("", "nan", "NaT", "None")
            )
            sb.append(f"  #{qr.row_index}")
            sb.append(f"    Data:            {row_preview[:80]}")
            sb.append(f"    Reason:          {qr.reason[:80]}")
            sb.append(f"    Category:        {qr.category}")
            sb.append(f"    Confidence:      {qr.confidence:.0%}")
            if qr.suggested_normalization:
                sb.append(f"    Suggestion:      {qr.suggested_normalization[:80]}")
            sb.append("")
    else:
        sb.append("  No problem records found.")
        sb.append("")
    sb.append("=" * 64)
    return "\n".join(sb)


__all__ = [
    "DataQualityMetrics",
    "QuarantineRecord",
    "ReportSummary",
    "build_report_summary",
    "format_report_txt",
]
