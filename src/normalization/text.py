from __future__ import annotations

import re
import unicodedata
from typing import List

try:
    import ftfy

    FTFY_AVAILABLE = True
except ImportError:
    FTFY_AVAILABLE = False

# Unicode blocks for multilingual support
_CYRILLIC_PATTERN = re.compile(r"[А-Яа-яЁё]+")
_ARABIC_PATTERN = re.compile(r"[\u0600-\u06FF\u0750-\u077F]+")
_CJK_PATTERN = re.compile(r"[\u4E00-\u9FFF\u3400-\u4DBF]+")
_DEVANAGARI_PATTERN = re.compile(r"[\u0900-\u097F]+")

_OCR_ARTIFACT_PATTERN = re.compile(r"[│┃║═╔╗╚╝╟╢╞╡╤╧╬╠╣|¦]{4,}")

_UNWANTED_CHARS_PATTERN = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b\u200c\u200d\ufeff\u00ad]")

_CONTROL_ESCAPE_PATTERN = re.compile(r"\\(?:[fcou][0-9a-fA-F]*|x[0-9a-fA-F]{2})")

_REPEATED_PUNCT_PATTERN = re.compile(r"([^\w\s])\1+")

_NUMBER_SEPARATOR_PATTERN = re.compile(r"(\d)\s+(?=\d)")


def fix_encoding(text: str) -> str:
    if not text:
        return ""
    if FTFY_AVAILABLE:
        return ftfy.fix_text(str(text))
    return unicodedata.normalize("NFC", str(text))


def normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_script(text: str) -> str:
    """Detect primary script of text."""
    if _CYRILLIC_PATTERN.search(text):
        return "cyrillic"
    if _ARABIC_PATTERN.search(text):
        return "arabic"
    if _CJK_PATTERN.search(text):
        return "cjk"
    if _DEVANAGARI_PATTERN.search(text):
        return "devanagari"
    return "latin"


def clean_ocr_artifacts(text: str) -> str:
    """Remove common OCR artifacts like box-drawing characters."""
    return _OCR_ARTIFACT_PATTERN.sub(" ", text)


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = str(text)

    if FTFY_AVAILABLE:
        text = ftfy.fix_text(text)
    else:
        text = unicodedata.normalize("NFC", text)

    text = clean_ocr_artifacts(text)
    text = _UNWANTED_CHARS_PATTERN.sub("", text)
    text = _CONTROL_ESCAPE_PATTERN.sub("", text)
    text = _REPEATED_PUNCT_PATTERN.sub(r"\1", text)
    text = _NUMBER_SEPARATOR_PATTERN.sub(r"\1", text)
    text = text.rstrip("\\").strip()
    text = re.sub(r"\s+", " ", text).strip()

    return text


def is_ocr_garbled(text: str, threshold: float = 0.4) -> bool:
    """Check if text appears to be garbled OCR output."""
    if not text or len(text) < 5:
        return False
    special = sum(1 for c in text if not c.isalnum() and not c.isspace())
    return special / len(text) > threshold


def detect_ambiguous_date(text: str) -> bool:
    """Detect if a string could be an ambiguous date (DD/MM vs MM/DD)."""
    m = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$", text.strip())
    if not m:
        return False
    p1, p2 = int(m.group(1)), int(m.group(2))
    return p1 <= 12 and p2 <= 12 and p1 != p2


def is_partially_corrupted(record: dict) -> List[str]:
    """Check a record for signs of partial corruption.

    Returns list of suspected issues (empty = clean).
    """
    issues: List[str] = []
    for key, value in record.items():
        if value is None:
            continue
        if isinstance(value, str):
            if not value.strip():
                continue
            if is_ocr_garbled(value):
                issues.append(f"OCR artifacts in '{key}'")
            elif len(value) > 500:
                issues.append(f"Unusually long value in '{key}' ({len(value)} chars)")
        elif isinstance(value, float) and value != value:
            issues.append(f"NaN value in '{key}'")
    return issues
