from __future__ import annotations

import re
import unicodedata

try:
    import ftfy

    FTFY_AVAILABLE = True
except ImportError:
    FTFY_AVAILABLE = False


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


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = str(text)

    if FTFY_AVAILABLE:
        text = ftfy.fix_text(text)
    else:
        text = unicodedata.normalize("NFC", text)

    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    text = re.sub(r"\\[fcou][0-9a-fA-F]*", "", text)
    text = re.sub(r"([^\w\s])\1+", r"\1", text)
    text = re.sub(r"(\d)\s+(?=\d)", r"\1", text)
    text = text.rstrip("\\").strip()
    text = re.sub(r"\s+", " ", text).strip()

    return text
