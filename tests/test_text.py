import pytest

from src.normalization.text import (
    clean_ocr_artifacts,
    detect_ambiguous_date,
    detect_script,
    fix_encoding,
    is_ocr_garbled,
    is_partially_corrupted,
    normalize_text,
    normalize_whitespace,
)

# fix_encoding


def test_fix_encoding_empty():
    assert fix_encoding("") == ""
    assert fix_encoding(None) == ""


def test_fix_encoding_fixes_mojibake():
    text = "ÐŸÑ€Ð¸Ð²ÐµÑ‚"
    assert fix_encoding(text).strip() != ""


def test_fix_encoding_fallback_nfc(monkeypatch):
    import src.normalization.text as mod

    monkeypatch.setattr(mod, "FTFY_AVAILABLE", False)
    result = fix_encoding("caf\u0065\u0301")
    assert result == "café"


# normalize_whitespace


def test_normalize_whitespace_collapses():
    assert normalize_whitespace("  a    b  ") == "a b"
    assert normalize_whitespace("") == ""
    assert normalize_whitespace(None) == ""


# detect_script


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Привет", "cyrillic"),
        ("مرحبا", "arabic"),
        ("你好", "cjk"),
        ("नमस्ते", "devanagari"),
        ("hello", "latin"),
    ],
)
def test_detect_script(text, expected):
    assert detect_script(text) == expected


# clean_ocr_artifacts


def test_clean_ocr_artifacts():
    assert "║═══║" not in clean_ocr_artifacts("a║═══║b")


# is_ocr_garbled


def test_is_ocr_garbled_short_text():
    assert not is_ocr_garbled("ab")
    assert not is_ocr_garbled("")


def test_is_ocr_garbled_detects():
    assert is_ocr_garbled("%%%####@@@")
    assert not is_ocr_garbled("clean normal text")


# detect_ambiguous_date


def test_detect_ambiguous_date():
    assert detect_ambiguous_date("01/02/2024")
    assert not detect_ambiguous_date("13/02/2024")
    assert not detect_ambiguous_date("not a date")
    assert not detect_ambiguous_date("")


# is_partially_corrupted


def test_partially_corrupted_clean():
    assert is_partially_corrupted({"name": "Alice", "age": 30}) == []


def test_partially_corrupted_none_skipped():
    assert is_partially_corrupted({"name": None}) == []


def test_partially_corrupted_ocr_garbled():
    issues = is_partially_corrupted({"name": "@@@###$$$"})
    assert any("OCR" in i for i in issues)


def test_partially_corrupted_long_value():
    issues = is_partially_corrupted({"name": "x" * 600})
    assert any("long" in i for i in issues)


def test_partially_corrupted_nan_float():
    issues = is_partially_corrupted({"amount": float("nan")})
    assert any("NaN" in i for i in issues)


def test_partially_corrupted_empty_string_skipped():
    assert is_partially_corrupted({"name": "  "}) == []


# normalize_text extra branches


def test_normalize_text_no_ftfy(monkeypatch):
    import src.normalization.text as mod

    monkeypatch.setattr(mod, "FTFY_AVAILABLE", False)
    assert normalize_text("caf\u0065\u0301").startswith("caf")


def test_normalize_text_control_escape():
    assert "\\x00" not in normalize_text("a\\x00b")


def test_normalize_text_trailing_backslash():
    result = normalize_text("value\\")
    assert not result.endswith("\\")
