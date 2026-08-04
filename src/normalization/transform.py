from __future__ import annotations

import logging
from typing import List, Optional, Set

import pandas as pd

from src.normalization.base import is_text_dtype

logger = logging.getLogger(__name__)

try:
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:
    pl = None
    POLARS_AVAILABLE = False


def _polars_strip(expr):
    """Strip whitespace from a Polars string expression across polars versions.

    ``str.strip`` was renamed to ``str.strip_chars`` in polars 1.x.
    """
    try:
        return expr.str.strip()
    except AttributeError:
        return expr.str.strip_chars()


def _series_to_polars_string(series) -> list:
    """Convert a pandas Series into a list of strings/None for a Polars column.

    Avoids ``DataFrame.fillna(None)`` which raises ``ValueError`` on pandas 2.x
    while preserving nulls as Polars nulls. Stringification is vectorised via
    the ``string`` dtype, so mixed or non-scalar cells (lists, dicts) cannot
    break the conversion; only a cheap identity pass normalises ``pd.NA``.
    """
    values = series.astype("string").tolist()
    return [None if v is pd.NA else v for v in values]


NULL_PATTERNS: Set[str] = {
    "",
    "null",
    "none",
    "na",
    "n/a",
    "nan",
    "-",
    "?",
    "undefined",
    "nil",
    "unknown",
}


class PolarsTransformer:
    """Internal transformation engine leveraging Polars for intelligent data processing.

    Converts between pandas and Polars internally; all inputs/outputs remain
    pandas DataFrames to preserve the existing Fluent API contract.

    Designed to be used inside normalization stages (NormalizeStage, CleanStage)
    without requiring any public API changes.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self._pdf = df
        self._type_conversion_failures: int = 0
        self._null_count: int = 0
        self._null_rate: float = 0.0
        self._schema_drift_detected: bool = False

    # Public metrics

    @property
    def type_conversion_failures(self) -> int:
        return self._type_conversion_failures

    @property
    def null_rate(self) -> float:
        return self._null_rate

    @property
    def schema_drift_detected(self) -> bool:
        return self._schema_drift_detected

    # Full pipeline

    def transform(self) -> pd.DataFrame:
        """Apply the full intelligent transformation pipeline.

        Steps:
        1. Detect & standardise null-like values
        2. Infer schema & safely coerce types (int / float / str)
        3. Parse date-like string columns
        4. Normalise numeric formats (European decimals, currency)
        5. Normalise text (Unicode cleanup, multilingual)
        6. Handle mixed-type columns
        """
        df = self._pdf.copy()
        if df.empty:
            return df
        df = self._detect_and_mark_nulls(df)
        df = self._coerce_types(df)
        df = self._parse_dates(df)
        df = self._normalise_numbers(df)
        df = self._clean_text_columns(df)
        df = self._handle_mixed_types(df)
        return df

    # Step 1: Null detection

    def _detect_and_mark_nulls(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in df.columns:
            if is_text_dtype(df[col].dtype):
                cleaned = df[col].astype(str).str.strip().str.lower()
                mask = cleaned.isin(NULL_PATTERNS)
                self._null_count += int(mask.sum())
                df.loc[mask, col] = None
        total_cells = max(df.size, 1)
        self._null_rate = self._null_count / total_cells
        return df

    # Step 2: Schema inference & type coercion

    def _coerce_types(self, df: pd.DataFrame) -> pd.DataFrame:
        if POLARS_AVAILABLE and pl is not None:
            return self._coerce_types_polars(df)
        return self._coerce_types_pandas(df)

    def _coerce_types_polars(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in df.columns:
            if not is_text_dtype(df[col].dtype) or df[col].dropna().empty:
                continue
            series = df[col].dropna()
            sample = series.head(100)
            try:
                pldf = pl.DataFrame({col: _series_to_polars_string(sample)})
                # Polars schema inference
                inferred = pldf.with_columns(_polars_strip(pl.col(col).cast(pl.String)))
                # Try integer
                try:
                    as_int = inferred.with_columns(pl.col(col).cast(pl.Int64, strict=False).alias("_cast"))
                    non_null_int = as_int.filter(pl.col("_cast").is_not_null()).height
                    total = inferred.height
                    if total > 0 and non_null_int / total > 0.6:
                        full_pldf = pl.DataFrame({col: _series_to_polars_string(df[col])})
                        full_pldf = full_pldf.with_columns(_polars_strip(pl.col(col).cast(pl.String)))
                        full_pldf = full_pldf.with_columns(pl.col(col).cast(pl.Int64, strict=False))
                        pandas_col = full_pldf[col].to_pandas()
                        failed = pandas_col.isna().sum() - df[col].isna().sum()
                        self._type_conversion_failures += int(failed)
                        df[col] = pandas_col
                        continue
                except Exception as exc:
                    logger.debug("int coercion skipped for %r: %s", col, exc)
                # Try float
                try:
                    as_float = inferred.with_columns(pl.col(col).cast(pl.Float64, strict=False).alias("_cast"))
                    non_null_float = as_float.filter(pl.col("_cast").is_not_null()).height
                    total = inferred.height
                    if total > 0 and non_null_float / total > 0.6:
                        full_pldf = pl.DataFrame({col: _series_to_polars_string(df[col])})
                        full_pldf = full_pldf.with_columns(_polars_strip(pl.col(col).cast(pl.String)))
                        full_pldf = full_pldf.with_columns(pl.col(col).cast(pl.Float64, strict=False))
                        pandas_col = full_pldf[col].to_pandas()
                        failed = pandas_col.isna().sum() - df[col].isna().sum()
                        self._type_conversion_failures += int(failed)
                        df[col] = pandas_col
                        continue
                except Exception as exc:
                    logger.debug("float coercion skipped for %r: %s", col, exc)
            except Exception as exc:
                logger.debug("schema inference skipped for %r: %s", col, exc)
                continue
        return df

    def _coerce_types_pandas(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in df.columns:
            if not is_text_dtype(df[col].dtype) or df[col].dropna().empty:
                continue
            series = df[col].dropna()
            if series.empty:
                continue
            try:
                num = pd.to_numeric(series, errors="raise")
                if num.apply(float.is_integer).all():
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                    continue
            except (ValueError, TypeError):
                pass
            new_col = pd.to_numeric(df[col], errors="coerce")
            non_null_before = df[col].notna().sum()
            non_null_after = new_col.notna().sum()
            ratio = non_null_after / max(non_null_before, 1)
            if ratio > 0.6:
                failed = non_null_before - non_null_after
                self._type_conversion_failures += int(max(failed, 0))
                df[col] = new_col
        return df

    # Step 3: Date parsing

    def _parse_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        if POLARS_AVAILABLE and pl is not None:
            return self._parse_dates_polars(df)
        return self._parse_dates_pandas(df)

    def _parse_dates_polars(self, df: pd.DataFrame) -> pd.DataFrame:
        date_formats: List[str] = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%Y.%m.%d",
            "%d.%m.%Y",
            "%Y%m%d",
            "%d %b %Y",
            "%d %B %Y",
            "%B %d %Y",
        ]
        for col in df.columns:
            if not is_text_dtype(df[col].dtype) or df[col].dropna().empty:
                continue
            try:
                pldf = pl.DataFrame({col: _series_to_polars_string(df[col])})
                pldf = pldf.with_columns(_polars_strip(pl.col(col).cast(pl.String)))
                best_fmt: Optional[str] = None
                best_count = 0
                for fmt in date_formats:
                    try:
                        parsed = pldf.with_columns(pl.col(col).str.to_date(format=fmt, strict=False))
                        valid = parsed.filter(pl.col(col).is_not_null()).height
                        if valid > best_count:
                            best_count = valid
                            best_fmt = fmt
                    except Exception as exc:
                        logger.debug("date format %r failed for %r: %s", fmt, col, exc)
                if best_fmt and best_count > len(df) * 0.3:
                    parsed = pldf.with_columns(pl.col(col).str.to_date(format=best_fmt, strict=False))
                    df[col] = parsed[col].to_pandas()
            except Exception as exc:
                logger.debug("date parsing skipped for %r: %s", col, exc)
                continue
        return df

    def _parse_dates_pandas(self, df: pd.DataFrame) -> pd.DataFrame:
        date_formats: List[str] = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%Y.%m.%d",
            "%d.%m.%Y",
            "%Y%m%d",
        ]
        for col in df.columns:
            if not is_text_dtype(df[col].dtype) or df[col].dropna().empty:
                continue
            if df[col].str.len().max() < 25:
                best_fmt: Optional[str] = None
                best_count = 0
                for fmt in date_formats:
                    try:
                        parsed = pd.to_datetime(df[col], format=fmt, errors="coerce")
                        valid = parsed.notna().sum()
                        if valid > best_count:
                            best_count = valid
                            best_fmt = fmt
                    except Exception:
                        continue
                if best_fmt and best_count > len(df) * 0.3:
                    df[col] = pd.to_datetime(df[col], format=best_fmt, errors="coerce")
                    continue
        return df

    # Step 4: Number normalisation

    def _normalise_numbers(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in df.columns:
            if not is_text_dtype(df[col].dtype):
                continue
            series = df[col].astype(str)
            non_null = series[series.notna() & (series != "")]
            if non_null.empty:
                continue
            eu_pattern = non_null.str.match(r"^\d{1,3}(\.\d{3})*,\d+$")
            if eu_pattern.any():
                cleaned = (
                    series.str.replace(r"\.(?=\d{3})", "", regex=True)
                    .str.replace(",", ".")
                    .str.replace(r"\s", "", regex=True)
                )
                df[col] = pd.to_numeric(cleaned, errors="coerce")
                continue
            has_currency = non_null.str.contains(r"[$€£¥₹₽]").any()
            if has_currency:
                cleaned = series.str.replace(r"[$€£¥₹₽,\s]", "", regex=True)
                numeric = pd.to_numeric(cleaned, errors="coerce")
                clean_ratio = numeric.notna().sum() / max(len(non_null), 1)
                if clean_ratio >= 0.5:
                    df[col] = numeric
                    continue
        return df

    # Step 5: Text cleaning (Unicode, multilingual)

    def _clean_text_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in df.columns:
            if is_text_dtype(df[col].dtype):
                df[col] = df[col].apply(lambda x: self._clean_text(x) if isinstance(x, str) else x)
        return df

    @staticmethod
    def _clean_text(text: str) -> str:
        from src.normalization.text import normalize_text

        return normalize_text(text)

    # Step 6: Mixed-type column handling

    def _handle_mixed_types(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in df.columns:
            if is_text_dtype(df[col].dtype) and not df[col].dropna().empty:
                non_null = df[col].dropna()
                type_counts = non_null.apply(type).value_counts()
                num_types = len(type_counts)
                counts = dict(zip(type_counts.index, type_counts.values))
                str_count = int(counts.get(str, 0))
                if num_types > 1 and str_count > 0:
                    self._schema_drift_detected = True
                    numeric = pd.to_numeric(df[col].astype(str), errors="coerce")
                    if numeric.notna().sum() > len(df) * 0.5:
                        df[col] = numeric
        return df
