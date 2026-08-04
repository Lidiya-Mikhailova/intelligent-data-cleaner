from __future__ import annotations

import re
from typing import List, Tuple

import pandas as pd

from src.forms.base import BaseFormExtractor
from src.forms.registry import register_form

F1099_DETECT_RE = re.compile(r"Form\s+1099|1099\s*[-−—]\s*(NEC|MISC|INT|DIV|R|K)", re.IGNORECASE)

F1099_FIELD_MAP: List[Tuple[str, str]] = [
    (r"payer\s+name", "payer_name"),
    (r"payer\s+address", "payer_address"),
    (r"payer\s+id(?:entification)?\s*number", "payer_ein"),
    (r"recipient\s+name", "recipient_name"),
    (r"recipient\s+address", "recipient_address"),
    (r"recipient\s+id(?:entification)?\s*number", "recipient_tin"),
    (r"nonemployee\s+compensation", "nonemployee_comp"),
    (r"rents?", "rents"),
    (r"interest\s+income", "interest_income"),
    (r"dividends?", "dividends"),
    (r"federal\s+income\s+tax\s+withheld", "federal_tax_withheld"),
    (r"state\s+tax\s+withheld", "state_tax_withheld"),
    (r"gross\s+proceeds", "gross_proceeds"),
    (r"customer\s+name", "customer_name"),
    (r"customer\s+id", "customer_id"),
    (r"account\s+number", "account_number"),
]


@register_form("1099")
class F1099Extractor(BaseFormExtractor):
    name = "1099"

    def detect(self, text: str) -> bool:
        return bool(F1099_DETECT_RE.search(text))

    def extract(self, lines: List[str]) -> pd.DataFrame:
        rows: List[Tuple[str, str, str]] = []
        matched_lines = set()

        for pattern, field_name in F1099_FIELD_MAP:
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
