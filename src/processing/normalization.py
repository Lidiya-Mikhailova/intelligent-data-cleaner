import re
import unicodedata


def smart_normalize_text(text: str) -> str:
    """
    Normalize and clean a text string intelligently.

    Steps:
    1. Apply Unicode normalization (NFC)
    2. Remove control characters
    3. Collapse repeated punctuation (e.g., @@ -> @)
    4. Remove spaces inside numbers (like phone numbers)
    5. Capitalize words properly

    Args:
        text (str): Input string.

    Returns:
        str: Cleaned and normalized string.
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFC", str(text))
    text = re.sub(r"[\x00-\x1F\x7F]", "", text)
    text = re.sub(r'([^\w\s])\1+', r'\1', text)
    text = re.sub(r'(\d)\s+(?=\d)', r'\1', text)
    text = re.sub(r"\s+", " ", text).strip()

    parts = re.split(r"(\s+|-)", text)
    return "".join(
        p.capitalize() if p.strip() and p not in {" ", "-"} else p
        for p in parts
    )
