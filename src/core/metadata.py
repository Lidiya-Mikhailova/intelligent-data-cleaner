from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ProcessingStep:
    """Record of a single processing step applied to a document."""

    name: str
    timestamp: datetime = field(default_factory=datetime.now)
    params: Dict[str, Any] = field(default_factory=dict)
    rows_before: int = 0
    rows_after: int = 0
    status: str = "success"


@dataclass
class DocumentMetadata:
    """Metadata for a document — source, processing history, stats."""

    source: Optional[str] = None
    source_format: Optional[str] = None
    source_size_bytes: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    row_count: int = 0
    column_count: int = 0
    columns: List[str] = field(default_factory=list)
    processing_history: List[ProcessingStep] = field(default_factory=list)
    custom: Dict[str, Any] = field(default_factory=dict)
    quality_metrics: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: ProcessingStep) -> None:
        self.processing_history.append(step)
        self.modified_at = datetime.now()

    @property
    def processing_stages(self) -> List[str]:
        return [s.name for s in self.processing_history]

    @property
    def is_processed(self) -> bool:
        return len(self.processing_history) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "source_format": self.source_format,
            "source_size_bytes": self.source_size_bytes,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": self.columns,
            "processing_stages": self.processing_stages,
            "custom": self.custom,
            "quality_metrics": self.quality_metrics,
        }
