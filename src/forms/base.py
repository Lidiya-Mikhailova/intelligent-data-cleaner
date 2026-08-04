from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple

import pandas as pd


class BaseFormExtractor(ABC):
    name: str = ""

    @abstractmethod
    def detect(self, text: str) -> bool: ...

    @abstractmethod
    def extract(self, lines: List[str]) -> pd.DataFrame: ...

    def _make_df(self, rows: List[Tuple[str, str, str]]) -> pd.DataFrame:
        return pd.DataFrame(rows, columns=["Field", "Value", "SourceLine"])
