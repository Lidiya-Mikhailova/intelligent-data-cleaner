from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.document import Document


class ProcessingStage(ABC):
    name: str = "base"

    @abstractmethod
    def process(self, doc: Document) -> Document:
        ...

    def __repr__(self) -> str:
        return f"<Stage: {self.name}>"
