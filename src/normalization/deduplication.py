from __future__ import annotations

import logging
import re
from typing import List, Set, Tuple

import pandas as pd

try:
    from rapidfuzz import fuzz

    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

logger = logging.getLogger(__name__)


def normalize_key(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    return re.sub(r"[^\wА-Яа-я0-9]", "", text)


def fuzzy_deduplicate(
    values: List[str],
    threshold: float = 85.0,
) -> List[Tuple[str, str]]:
    if not RAPIDFUZZ_AVAILABLE:
        logger.warning("rapidfuzz not available, using exact matching only")
        seen: Set[str] = set()
        result: List[Tuple[str, str]] = []
        for v in values:
            key = normalize_key(v)
            if key and key not in seen:
                seen.add(key)
                result.append((v, v))
        return result

    seen: List[str] = []
    result: List[Tuple[str, str]] = []

    for v in values:
        if not v:
            continue
        matched = False
        for existing in seen:
            ratio = fuzz.token_sort_ratio(v.lower(), existing.lower())
            if ratio >= threshold:
                result.append((v, existing))
                matched = True
                break
        if not matched:
            seen.append(v)
            result.append((v, v))

    return result


def exact_deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df["_dup_key"] = df.apply(
        lambda row: "".join(normalize_key(str(x)) for x in row),
        axis=1,
    )
    result = (
        df.drop_duplicates(subset=["_dup_key"])
        .drop(columns=["_dup_key"])
        .reset_index(drop=True)
    )
    return result
