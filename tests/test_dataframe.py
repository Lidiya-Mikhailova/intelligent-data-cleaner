import pandas as pd

from src.normalization.deduplication import exact_deduplicate
from src.normalization.structural import normalize_dataframe


def test_deduplication():
    df = pd.DataFrame(
        {
            "name": ["John Doe", "john doe", "John Doe"],
            "email": ["john@example.com", "john@example.com", "john@example.com"],
        }
    )
    result = exact_deduplicate(normalize_dataframe(df))
    assert len(result) == 1


def test_normalization_applied():
    df = pd.DataFrame(
        {
            "name": ["  HELLO  world  "],
        }
    )
    result = normalize_dataframe(df)
    assert result["name"].iloc[0] == "HELLO world"


def test_empty_dataframe():
    df = pd.DataFrame()
    result = normalize_dataframe(df)
    assert len(result) == 0


def test_dup_key_removed():
    df = pd.DataFrame(
        {
            "name": ["Alice", "Bob"],
            "age": ["30", "25"],
        }
    )
    result = exact_deduplicate(normalize_dataframe(df))
    assert "_dup_key" not in result.columns


def test_numbers_spaces_removed():
    df = pd.DataFrame(
        {
            "phone": ["123 456 7890"],
        }
    )
    result = normalize_dataframe(df)
    assert "1234567890" in result["phone"].iloc[0]
