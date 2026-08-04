from __future__ import annotations

import logging

import pandas as pd

from .transform import PolarsTransformer

logger = logging.getLogger(__name__)


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply structural normalisation using the Polars transformation engine.

    Steps:
    1. Clean column names
    2. Polars-based type inference, coercion, date parsing, number normalisation
    3. Remove fully-empty rows
    """
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    transformer = PolarsTransformer(df)
    df = transformer.transform()

    df = df[(df.notna().any(axis=1))]

    return df.reset_index(drop=True)


def structural_metrics(df: pd.DataFrame) -> dict:
    """Compute structural quality metrics for a DataFrame."""
    transformer = PolarsTransformer(df)
    transformer.transform()

    return {
        "type_conversion_failures": transformer.type_conversion_failures,
        "null_rate": transformer.null_rate,
        "schema_drift_detected": transformer.schema_drift_detected,
        "conversion_report": transformer.conversion_report,
    }
