from src.normalization.text import normalize_text


def test_empty_string():
    assert normalize_text("") == ""
    assert normalize_text(None) == ""


def test_unicode_normalization():
    text = "caf\u0065\u0301"
    result = normalize_text(text)
    assert "caf" in result.lower()


def test_control_characters_removed():
    text = "hello\x00world\x1f"
    result = normalize_text(text)
    assert "\x00" not in result
    assert "\x1f" not in result


def test_repeated_punctuation_collapsed():
    result = normalize_text("hello@@world")
    assert "@@" not in result
    assert "hello@world" == result


def test_spaces_in_numbers_removed():
    result = normalize_text("123 456 789")
    assert "123456789" in result


def test_extra_whitespace_collapsed():
    result = normalize_text("hello    world")
    assert "  " not in result
