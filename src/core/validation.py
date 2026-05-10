from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from src.validation.models import SilverRecord, quarantine_warnings

logger = logging.getLogger(__name__)


def _validate_record(row: dict) -> tuple[bool, Optional[str]]:
    try:
        SilverRecord(**row)
        return True, None
    except Exception as e:
        return False, str(e)


def classify_records(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Validate and classify DataFrame records into VALID / INVALID / QUARANTINE.

    Returns:
        (valid_df, invalid_df, quarantine_df)
    """

    valid_rows: list[dict] = []
    invalid_rows: list[dict] = []
    quarantine_rows: list[dict] = []

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        is_valid, error = _validate_record(row_dict)

        if is_valid:
            warnings = quarantine_warnings(row_dict)
            if warnings:
                row_dict["quarantine_reasons"] = "; ".join(warnings)
                quarantine_rows.append(row_dict)
            else:
                valid_rows.append(row_dict)
        else:
            row_dict["validation_error"] = error or "Unknown validation error"
            invalid_rows.append(row_dict)

    return (
        pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame(),
        pd.DataFrame(invalid_rows) if invalid_rows else pd.DataFrame(),
        pd.DataFrame(quarantine_rows) if quarantine_rows else pd.DataFrame(),
    )
