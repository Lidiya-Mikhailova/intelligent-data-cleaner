from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.document import Document


def is_text_dtype(dtype) -> bool:
    """Return True for text/string column dtypes across pandas 2.x and 3.x.

    pandas 2.x stores strings as ``object``; pandas 3.x defaults to the
    ``str`` dtype (an instance of ``pd.StringDtype``).
    """
    from pandas.api.types import is_string_dtype

    return is_string_dtype(dtype)


class ProcessingStage(ABC):
    name: str = "base"

    @abstractmethod
    def process(self, doc: Document) -> Document:
        ...

    def __repr__(self) -> str:
        return f"<Stage: {self.name}>"
