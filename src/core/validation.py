from __future__ import annotations

import json
import logging
from typing import Optional, Tuple

import pandas as pd

from src.dq import DQ_COLUMNS, strip_dq_columns
from src.validation.models import SilverRecord, quarantine_warnings

logger = logging.getLogger(__name__)


def _validate_record(row: dict) -> Tuple[bool, Optional[str]]:
    try:
        SilverRecord(**row)
        return True, None
    except Exception as e:
        return False, str(e)


def _parse_checks(raw) -> list[dict]:
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


def _has_dq_critical(checks: list[dict]) -> bool:
    for c in checks:
        if c.get("status") == "fail" and c.get("severity") in ("error", "critical"):
            return True
    return False


def classify_records(
    df: pd.DataFrame,
    strict: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Validate and classify DataFrame records into VALID / INVALID / QUARANTINE.

    When ``strict=True`` (default), uses Pydantic ``SilverRecord`` validation
    and DQ metadata.  When ``strict=False``, skips schema validation and only
    uses DQ status — rows without DQ issues go to VALID.

    DQ columns (``_dq_score``, ``_dq_status``, ``_dq_checks``) are stripped
    before Pydantic validation but their status influences the final routing:

        - Pydantic INVALID / DQ critical -> INVALID  (only when strict=True)
        - DQ status "warn" or quarantine_warnings -> QUARANTINE
        - Everything else -> VALID

    Returns:
        (valid_df, invalid_df, quarantine_df)
    """
    valid_rows: list[dict] = []
    invalid_rows: list[dict] = []
    quarantine_rows: list[dict] = []

    clean_df = strip_dq_columns(df)
    row_records = df.to_dict("records")
    clean_records = clean_df.to_dict("records")
    if DQ_COLUMNS[2] in df.columns:
        parsed_checks = df[DQ_COLUMNS[2]].map(_parse_checks).tolist()
    else:
        parsed_checks = [[] for _ in range(len(df))]
    if DQ_COLUMNS[1] in df.columns:
        dq_status_list = df[DQ_COLUMNS[1]].tolist()
    else:
        dq_status_list = [None] * len(df)
    dq_critical_list = [_has_dq_critical(checks) for checks in parsed_checks]

    for row_dict, clean_row, dq_status, dq_critical, dq_issues in zip(
        row_records, clean_records, dq_status_list, dq_critical_list, parsed_checks
    ):

        if strict:
            is_valid, error = _validate_record(clean_row)
            if not is_valid:
                row_dict["validation_error"] = error or "Unknown validation error"
                invalid_rows.append(row_dict)
                continue

        dq_reasons = [f"[DQ:{c['check_name']}] {c['message']}" for c in dq_issues if c["status"] in ("warn", "fail")]

        if dq_critical:
            row_dict["validation_error"] = "; ".join(dq_reasons) if dq_reasons else "DQ critical failure"
            invalid_rows.append(row_dict)
            continue

        warnings = quarantine_warnings(clean_row)
        if dq_status == "warn":
            if dq_reasons:
                warnings.extend(dq_reasons)

        if warnings:
            row_dict["quarantine_reasons"] = "; ".join(warnings)
            quarantine_rows.append(row_dict)
        else:
            valid_rows.append(row_dict)

    return (
        pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame(),
        pd.DataFrame(invalid_rows) if invalid_rows else pd.DataFrame(),
        pd.DataFrame(quarantine_rows) if quarantine_rows else pd.DataFrame(),
    )
