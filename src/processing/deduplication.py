import re


def normalize_for_strict_duplicates(text: str) -> str:
    """
    Generate a strict key for duplicate detection.

    Steps:
    1. Convert to lowercase
    2. Remove all non-alphanumeric characters

    Args:
        text (str): Input string.

    Returns:
        str: String suitable for strict duplicate comparison.
    """
    if not text:
        return ""
    text = text.lower()
    return re.sub(r"[^\wА-Яа-я0-9]", "", text)
