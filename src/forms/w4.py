from __future__ import annotations

import re
from typing import List, Tuple

import pandas as pd

from src.forms.base import BaseFormExtractor
from src.forms.registry import register_form

W4_DETECT_RE = re.compile(r"Form\s+W[−—\-]\s*4|W\s*[-−—]\s*4\s+Employee", re.IGNORECASE)

W4_FIELD_MAP: List[Tuple[str, str]] = [
    (r"first\s+name\s+and\s+middle\s+initial", "first_name_middle_initial"),
    (r"last\s+name", "last_name"),
    (r"address.*?\(.*?number\s+and\s+street.*?\)", "address"),
    (r"city\s+or\s+town", "city"),
    (r"state", "state"),
    (r"zip\s+code", "zip_code"),
    (r"social\s+security\s+number", "ssn"),
    (r"single\b", "filing_status_single"),
    (r"married\s+filing\s+jointly", "filing_status_married_joint"),
    (r"married\s+filing\s+separately", "filing_status_married_separate"),
    (r"head\s+of\s+household", "filing_status_head_household"),
    (r"qualifying\s+widow(?:er)?", "filing_status_qualifying_widow"),
    (r"total\s+amount\s+of\s+income", "total_income"),
    (r"dependents?", "dependents"),
    (r"other\s+income", "other_income"),
    (r"deductions?", "deductions"),
    (r"signature", "signature"),
    (r"date\s*[:\-]?\s*\d|date\b", "date"),
    (r"employer\s+name", "employer_name"),
    (r"employer\s+id(?:entification)?\s*(?:number)?", "ein"),
]


@register_form("w4")
class W4Extractor(BaseFormExtractor):
    name = "w4"

    def detect(self, text: str) -> bool:
        return bool(W4_DETECT_RE.search(text))

    def extract(self, lines: List[str]) -> pd.DataFrame:
        rows: List[Tuple[str, str, str]] = []
        matched_lines = set()

        for pattern, field_name in W4_FIELD_MAP:
            regex = re.compile(pattern, re.IGNORECASE)
            for i, line in enumerate(lines):
                if i in matched_lines:
                    continue
                if regex.search(line):
                    rows.append((field_name, "", line))
                    matched_lines.add(i)
                    break

        for i, line in enumerate(lines):
            if i not in matched_lines and line.strip():
                rows.append(("Text", line.strip(), line.strip()))

        return self._make_df(rows)
