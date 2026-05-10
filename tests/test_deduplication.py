from src.normalization.deduplication import normalize_key


def test_lowercase():
    assert normalize_key("HELLO") == "hello"


def test_removes_punctuation():
    assert normalize_key("hello, world!") == "helloworld"


def test_preserves_cyrillic():
    result = normalize_key("Привет Мир")
    assert "привет" in result
    assert "мир" in result


def test_preserves_numbers():
    assert normalize_key("abc123") == "abc123"


def test_empty_string():
    assert normalize_key("") == ""
    assert normalize_key(None) == ""
