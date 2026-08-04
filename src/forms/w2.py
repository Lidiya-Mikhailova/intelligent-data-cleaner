from __future__ import annotations

import re
from typing import List, Tuple

import pandas as pd

from src.forms.base import BaseFormExtractor
from src.forms.registry import register_form

W2_DETECT_RE = re.compile(r"Form\s+W[−—\-]\s*2|W\s*[-−—]\s*2\s+(Wage|Wages|Tax)", re.IGNORECASE)

W2_FIELD_MAP: List[Tuple[str, str]] = [
    (r"employer\s+(?:identification\s+)?number", "ein"),
    (r"employer\s+name", "employer_name"),
    (r"employer\s+address", "employer_address"),
    (r"control\s+number", "control_number"),
    (r"social\s+security\s+number", "ssn"),
    (r"employee\s+name", "employee_name"),
    (r"employee\s+address", "employee_address"),
    (r"wages,\s+(?:tips\s+)?other\s+compensation", "wages_tips_comp"),
    (r"social\s+security\s+wages", "ss_wages"),
    (r"social\s+security\s+tax\s+withheld", "ss_tax_withheld"),
    (r"medicare\s+wages\s+and\s+tips", "medicare_wages_tips"),
    (r"medicare\s+tax\s+withheld", "medicare_tax_withheld"),
    (r"federal\s+income\s+tax\s+withheld", "federal_tax_withheld"),
    (r"state\s+wages", "state_wages"),
    (r"state\s+income\s+tax", "state_tax"),
    (r"local\s+wages", "local_wages"),
    (r"local\s+income\s+tax", "local_tax"),
]


@register_form("w2")
class W2Extractor(BaseFormExtractor):
    name = "w2"

    def detect(self, text: str) -> bool:
        return bool(W2_DETECT_RE.search(text))

    def extract(self, lines: List[str]) -> pd.DataFrame:
        rows: List[Tuple[str, str, str]] = []
        matched_lines = set()

        for pattern, field_name in W2_FIELD_MAP:
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
