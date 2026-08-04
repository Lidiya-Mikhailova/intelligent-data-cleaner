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


def _get_dq_status(row: dict) -> Optional[str]:
    return row.get(DQ_COLUMNS[1])


def _get_dq_checks_summary(row: dict) -> list[dict]:
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


def _has_dq_critical(row: dict) -> bool:
    checks = _get_dq_checks_summary(row)
    for c in checks:
        if c.get("status") == "fail" and c.get("severity") in ("error", "critical"):
            return True
    return False


def _has_dq_warn(row: dict) -> bool:
    checks = _get_dq_checks_summary(row)
    for c in checks:
        if c.get("status") == "warn":
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

    from src.normalization.transform import PolarsTransformer

    transformer = PolarsTransformer(df)
    _ = transformer.transform()

    for _, row in df.iterrows():
        row_dict = row.to_dict()

        dq_status = _get_dq_status(row_dict)
        dq_critical = _has_dq_critical(row_dict)

        clean_row = strip_dq_columns(pd.DataFrame([row_dict])).iloc[0].to_dict()

        if strict:
            is_valid, error = _validate_record(clean_row)
            if not is_valid:
                row_dict["validation_error"] = error or "Unknown validation error"
                invalid_rows.append(row_dict)
                continue

        dq_issues = _get_dq_checks_summary(row_dict)
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
