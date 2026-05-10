from __future__ import annotations

import logging

import pandas as pd

from .text import normalize_text

logger = logging.getLogger(__name__)


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    for col in df.columns:
        df[col] = df[col].apply(normalize_text)

    df = df[(df != "").any(axis=1)]

    return df.reset_index(drop=True)
