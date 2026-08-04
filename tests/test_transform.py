import pandas as pd
import pytest

from src.normalization.transform import NULL_PATTERNS, PolarsTransformer, _series_to_polars_string


@pytest.fixture
def transformer():
    def _make(df):
        return PolarsTransformer(df)

    return _make


# Polars bridge


def test_series_to_polars_string_preserves_nulls():
    result = _series_to_polars_string(pd.Series(["1", None, "3", float("nan")]))
    assert result == ["1", None, "3", None]


def test_series_to_polars_string_handles_non_scalar_cells():
    result = _series_to_polars_string(pd.Series([{"a": 1}, [1, 2], "x"]))
    assert result == ["{'a': 1}", "[1, 2]", "x"]


# Empty / trivial inputs


def test_transform_empty_df(transformer):
    df = pd.DataFrame()
    result = transformer(df).transform()
    assert result.empty


def test_transform_single_row_pass_through(transformer):
    df = pd.DataFrame({"Name": ["Alice"], "Age": ["30"]})
    result = transformer(df).transform()
    assert list(result.columns) == ["Name", "Age"]


# Null detection


@pytest.mark.parametrize("bad_value", ["N/A", "NULL", "None", "nan", "-", "?"])
def test_null_patterns_marked(transformer, bad_value):
    df = pd.DataFrame({"A": ["x", bad_value, "y"], "B": ["1", "2", "3"]})
    t = transformer(df)
    result = t.transform()
    assert result["A"].isna().sum() == 1
    assert t.null_rate > 0


def test_null_patterns_set_contains_sentinels():
    assert "null" in NULL_PATTERNS
    assert "undefined" in NULL_PATTERNS


# Type coercion


def test_integer_coercion(transformer):
    df = pd.DataFrame({"ID": ["42", "7", "13", "99", "2"]})
    result = transformer(df).transform()
    assert str(result["ID"].dtype).startswith("Int") or result["ID"].dtype == "int64"


def test_integer_coercion_with_missing_converts_rest(transformer):
    df = pd.DataFrame({"ID": ["42", "7", "not-a-number", "13", "2"]})
    t = transformer(df)
    result = t.transform()
    assert result["ID"].notna().sum() == 4
    assert t.type_conversion_failures >= 1


def test_float_coercion(transformer):
    df = pd.DataFrame({"Val": ["1.5", "2.5", "3.5", "4.5", "5.5"]})
    result = transformer(df).transform()
    assert pd.api.types.is_float_dtype(result["Val"])


def test_mostly_text_stays_text(transformer):
    df = pd.DataFrame({"Name": ["Alice", "Bob", "Carol", "Dan", "Eve"]})
    result = transformer(df).transform()
    assert result["Name"].dtype == object or "str" in str(result["Name"].dtype)


def test_non_text_column_untouched(transformer):
    df = pd.DataFrame({"Num": [1, 2, 3]})
    result = transformer(df).transform()
    assert result["Num"].tolist() == [1, 2, 3]


# Date parsing


def test_date_parsing_iso(transformer):
    df = pd.DataFrame({"Date": ["2024-01-15", "2024-02-20", "2024-03-25", "2024-04-10"]})
    result = transformer(df).transform()
    assert pd.api.types.is_datetime64_any_dtype(result["Date"])


def test_date_parsing_eu_format(transformer):
    df = pd.DataFrame({"Date": ["15/01/2024", "20/02/2024", "25/03/2024", "10/04/2024"]})
    result = transformer(df).transform()
    assert pd.api.types.is_datetime64_any_dtype(result["Date"])


def test_mixed_dates_not_converted(transformer):
    df = pd.DataFrame({"Date": ["not-a-date", "also-not", "nope", "nah"]})
    result = transformer(df).transform()
    assert not pd.api.types.is_datetime64_any_dtype(result["Date"])


# Number normalisation


def test_eu_decimal_normalisation(transformer):
    df = pd.DataFrame({"Price": ["1.234,56", "2.345,67", "3.456,78", "4.567,89", "5.678,90"]})
    result = transformer(df).transform()
    assert result["Price"].tolist()[0] == pytest.approx(1234.56)


def test_currency_normalisation(transformer):
    df = pd.DataFrame({"Price": ["$1,200.50", "€2,300.00", "$3,400.00", "$4,500.00", "$5,600.00"]})
    result = transformer(df).transform()
    assert result["Price"].iloc[0] == pytest.approx(1200.50)


# Text cleaning


def test_text_cleaning_applied(transformer):
    df = pd.DataFrame({"Name": ["  Alice\u00a0  ", "  Bob   ", "Carol"]})
    result = transformer(df).transform()
    assert "\u00a0" not in str(result["Name"].iloc[0])


def test_text_cleaning_skips_non_strings(transformer):
    df = pd.DataFrame({"A": ["x", "y", "z"], "B": ["1", "2", "3"]})
    result = transformer(df).transform()
    assert result["B"].notna().all()


# Mixed types


def test_mixed_types_flagged(transformer):
    df = pd.DataFrame({"A": pd.Series([1, "two", 3, 4, "five"], dtype=object)})
    t = transformer(df)
    result = t.transform()
    assert t.schema_drift_detected
    assert result["A"].notna().sum() >= 3


def test_single_type_no_drift(transformer):
    df = pd.DataFrame({"A": ["1", "2", "3"]})
    t = transformer(df)
    t.transform()
    assert not t.schema_drift_detected


# Metrics


def test_metrics_defaults(transformer):
    t = transformer(pd.DataFrame({"A": ["1", "2"]}))
    assert t.type_conversion_failures == 0
    assert t.null_rate == 0.0
    assert not t.schema_drift_detected


# Pandas fallback paths (polars unavailable)


@pytest.fixture
def no_polars(monkeypatch):
    import src.normalization.transform as mod

    monkeypatch.setattr(mod, "POLARS_AVAILABLE", False)
    monkeypatch.setattr(mod, "pl", None)
    return mod


def test_pandas_fallback_integer_coercion(no_polars):
    df = pd.DataFrame({"ID": ["1", "2", "3"]})
    result = no_polars.PolarsTransformer(df).transform()
    assert pd.api.types.is_integer_dtype(result["ID"])
    assert result["ID"].tolist() == [1, 2, 3]


def test_pandas_fallback_float_integers_become_int(no_polars):
    df = pd.DataFrame({"ID": ["1.0", "2.0", "3.0"]})
    result = no_polars.PolarsTransformer(df).transform()
    assert pd.api.types.is_integer_dtype(result["ID"])


def test_pandas_fallback_partial_integer_failure_counted(no_polars):
    df = pd.DataFrame({"ID": ["1", "2", "x", "4"]})
    t = no_polars.PolarsTransformer(df)
    result = t.transform()
    assert result["ID"].notna().sum() == 3
    assert t.type_conversion_failures == 1


def test_pandas_fallback_date_parsing(no_polars):
    df = pd.DataFrame({"Date": ["2024-01-15", "2024-02-20", "2024-03-25", "2024-04-10"]})
    result = no_polars.PolarsTransformer(df).transform()
    assert pd.api.types.is_datetime64_any_dtype(result["Date"])


def test_pandas_fallback_non_dates_untouched(no_polars):
    df = pd.DataFrame({"Date": ["hello", "world", "foo", "bar"]})
    result = no_polars.PolarsTransformer(df).transform()
    assert not pd.api.types.is_datetime64_any_dtype(result["Date"])


def test_number_normalisation_skips_all_empty(no_polars):
    df = pd.DataFrame({"A": ["", "", ""]})
    t = no_polars.PolarsTransformer(df)
    result = t.transform()
    assert result["A"].notna().sum() == 0


def test_currency_low_clean_ratio_untouched(no_polars):
    df = pd.DataFrame({"A": ["$abc", "hello", "world", "x", "y"]})
    result = no_polars.PolarsTransformer(df).transform()
    assert str(result["A"].iloc[0]) == "$abc"
