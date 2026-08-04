from __future__ import annotations

import re
from typing import Any, List, Optional

from pydantic import BaseModel, field_validator, model_validator


class SilverRecord(BaseModel):
    """Pydantic model for validating silver layer records.

    Flexible enough to handle extra fields (preserved via model_config)
    while enforcing core constraints on known fields.
    """

    ID: int
    Name: str
    Age: Optional[int] = None
    Email: Optional[str] = None
    Address: Optional[str] = None
    Notes: Optional[str] = None

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def empty_str_to_none(cls, values: dict) -> dict:
        for field in ("Age", "Email", "Address", "Notes"):
            val = values.get(field)
            if isinstance(val, str) and val.strip() == "":
                values[field] = None
        return values

    @field_validator("ID", mode="before")
    @classmethod
    def coerce_id(cls, v: Any) -> int:
        if isinstance(v, float) and v == v:
            return int(v)
        if isinstance(v, str):
            stripped = v.strip()
            if stripped:
                return int(float(stripped))
            raise ValueError("ID must not be empty")
        return int(v)

    @field_validator("Name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name must not be empty")
        return v.strip()

    @field_validator("Age")
    @classmethod
    def age_must_be_reasonable(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 150):
            raise ValueError("Age must be between 0 and 150")
        return v

    @field_validator("Email")
    @classmethod
    def email_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        email_pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$"
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v


def quarantine_warnings(row: dict) -> List[str]:
    """Check a validated record for warning-level anomalies.

    Returns a list of warning messages. Empty list means the record is clean.
    Records with warnings are routed to the QUARANTINE layer
    for manual review instead of going directly to VALID.
    """
    warnings: List[str] = []

    age = row.get("Age")
    if age is not None:
        try:
            age_val = int(age) if not isinstance(age, int) else age
            if age_val == 0:
                warnings.append("Age is 0 (suspicious)")
            elif age_val > 100:
                warnings.append(f"Age is {age_val} (unusually high)")
        except (ValueError, TypeError):
            pass

    name = row.get("Name")
    if name and isinstance(name, str):
        stripped = name.strip()
        if len(stripped) <= 1:
            warnings.append(f"Name is too short: '{stripped}'")

    email = row.get("Email")
    if email and isinstance(email, str) and "@" in email:
        suspicious_tlds = {".tk", ".ml", ".ga", ".cf", ".gq"}
        domain_part = email.split("@")[-1]
        for tld in suspicious_tlds:
            if domain_part.endswith(tld):
                warnings.append(f"Email uses suspicious TLD: {tld}")
                break

    from src.normalization.text import (
        detect_ambiguous_date,
        is_ocr_garbled,
        is_partially_corrupted,
    )

    for key, value in row.items():
        if value is None or not isinstance(value, str):
            continue
        if detect_ambiguous_date(value):
            warnings.append(f"Ambiguous date format in '{key}': '{value}'")
        if is_ocr_garbled(value):
            warnings.append(f"OCR artifacts detected in '{key}'")
    corruption_issues = is_partially_corrupted(row)
    warnings.extend(corruption_issues)

    return warnings
