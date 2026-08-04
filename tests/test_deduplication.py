import pandas as pd

from src.normalization.deduplication import exact_deduplicate, fuzzy_deduplicate, normalize_key


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


# fuzzy_deduplicate


def test_fuzzy_keeps_distinct_values():
    mapping = fuzzy_deduplicate(["Alice", "Bob", "Carol"], threshold=95.0)
    assert all(orig == canon for orig, canon in mapping)


def test_fuzzy_groups_similar_values():
    mapping = fuzzy_deduplicate(["Acme Corporation", "ACME Corporation", "Other"], threshold=80.0)
    by_orig = dict(mapping)
    assert by_orig["ACME Corporation"] == "Acme Corporation"
    assert by_orig["Other"] == "Other"


def test_fuzzy_skips_empty_values():
    mapping = fuzzy_deduplicate(["", "  ", "Bob"], threshold=85.0)
    assert all(orig == canon for orig, canon in mapping)


def test_fuzzy_exact_match_groups():
    mapping = fuzzy_deduplicate(["Apple", "apple", "Banana"], threshold=90.0)
    by_orig = dict(mapping)
    assert by_orig["apple"] == "Apple"


def test_fuzzy_fallback_without_rapidfuzz(monkeypatch):
    import src.normalization.deduplication as mod

    monkeypatch.setattr(mod, "RAPIDFUZZ_AVAILABLE", False)
    mapping = fuzzy_deduplicate(["Acme Corp", "Banana", "Banana"], threshold=80.0)
    assert dict(mapping) == {"Acme Corp": "Acme Corp", "Banana": "Banana"}


# exact_deduplicate


def test_exact_deduplicate_removes_dupes():
    df = pd.DataFrame({"Name": ["Alice", "alice ", "Bob"]})
    result = exact_deduplicate(df)
    assert len(result) == 2


def test_exact_deduplicate_empty():
    df = pd.DataFrame()
    result = exact_deduplicate(df)
    assert result.empty


def test_exact_deduplicate_no_dupes():
    df = pd.DataFrame({"A": [1, 2, 3]})
    result = exact_deduplicate(df)
    assert len(result) == 3


def test_exact_deduplicate_preserves_cyrillic():
    df = pd.DataFrame({"Name": ["Иван", "иван", "Пётр"]})
    result = exact_deduplicate(df)
    assert len(result) == 2
