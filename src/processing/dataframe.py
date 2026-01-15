import pandas as pd
from .normalization import smart_normalize_text
from .deduplication import normalize_for_strict_duplicates


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean an entire DataFrame.

    Steps:
    1. Normalize all text columns
    2. Create a strict duplicate key
    3. Drop duplicate rows based on the key
    4. Reset index

    Args:
        df (pd.DataFrame): Input DataFrame.

    Returns:
        pd.DataFrame: Cleaned and deduplicated DataFrame.
    """
    for col in df.columns:
        df[col] = df[col].apply(smart_normalize_text)

    df["_dup_key"] = df.apply(
        lambda row: "".join(
            normalize_for_strict_duplicates(str(x)) for x in row
        ),
        axis=1,
    )

    return (
        df.drop_duplicates(subset=["_dup_key"])
        .drop(columns=["_dup_key"])
        .reset_index(drop=True)
    )

