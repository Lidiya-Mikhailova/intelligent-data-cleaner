from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pandas as pd

from src.core.metadata import DocumentMetadata, ProcessingStep

logger = logging.getLogger(__name__)

FULL_PIPELINE_STAGES = [
    "ingest",
    "form_detect",
    "extract",
    "normalize",
    "clean",
    "deduplicate",
    "translate",
    "enrich",
    "dq",
    "export",
]


class Document:
    """Fluent API for loading, cleaning, inspecting, and exporting tabular data.

    Usage:
        doc = Document.from_file("dirty.csv")
        doc = doc.normalize().clean().deduplicate()
        doc = doc.remove_rows([3, 7])        # optional manual fix
        doc.export("csv", output_path="clean.csv")
    """

    def __init__(
        self,
        data: pd.DataFrame,
        metadata: Optional[DocumentMetadata] = None,
    ):
        self._data = data
        self._metadata = metadata or DocumentMetadata()
        self._metadata.row_count = len(data)
        self._metadata.column_count = len(data.columns)
        self._metadata.columns = data.columns.tolist()
        self._last_export_result: Any = None
        self._removed: Dict[str, pd.DataFrame] = {}
        self._review_summary: Any = None
        self._quarantine_df: pd.DataFrame = pd.DataFrame()

    # ── Review / Quarantine API ────────────────────────────────────

    @property
    def review(self):
        return self._review_summary

    @review.setter
    def review(self, value):
        self._review_summary = value

    @property
    def quarantine(self) -> pd.DataFrame:
        return self._quarantine_df.copy()

    def classify(self, strict: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        from src.core.validation import classify_records
        from src.review import ReportSummary

        valid, invalid, quarantine = classify_records(self._data, strict=strict)
        self._review_summary = ReportSummary(
            source_file=self._metadata.source or "memory",
            pipeline_run_id=0,
            rows_total=len(self._data),
            rows_valid=len(valid),
            rows_invalid=len(invalid),
            rows_quarantine=len(quarantine),
        )
        self._quarantine_df = quarantine
        return valid, invalid, quarantine

    # ── Factory Methods ────────────────────────────────────────────

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> Document:
        from src.normalization.pipeline import Pipeline
        from src.normalization.stages import ExtractStage, IngestStage

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return Pipeline([IngestStage(path=path), ExtractStage()]).run(cls(pd.DataFrame()))

    @classmethod
    def from_text(cls, text: str) -> Document:
        from src.normalization.pipeline import Pipeline
        from src.normalization.stages import ExtractStage, IngestStage

        return Pipeline([IngestStage(source="text", data=text), ExtractStage()]).run(cls(pd.DataFrame()))

    @classmethod
    def from_dict(cls, data: Union[Dict, List[Dict]]) -> Document:
        from src.normalization.pipeline import Pipeline
        from src.normalization.stages import ExtractStage, IngestStage

        return Pipeline([IngestStage(source="dict", data=data), ExtractStage()]).run(cls(pd.DataFrame()))

    @classmethod
    def from_bytes(cls, data: bytes, format: str = "csv") -> Document:
        from src.normalization.pipeline import Pipeline
        from src.normalization.stages import ExtractStage, IngestStage

        return Pipeline([IngestStage(source="bytes", data=data, format=format), ExtractStage()]).run(
            cls(pd.DataFrame())
        )

    # ── Properties ─────────────────────────────────────────────────

    @property
    def data(self) -> pd.DataFrame:
        return self._data.copy()

    @property
    def metadata(self) -> DocumentMetadata:
        return self._metadata

    @property
    def shape(self) -> Tuple[int, int]:
        return self._data.shape

    @property
    def columns(self) -> List[str]:
        return self._data.columns.tolist()

    @property
    def is_empty(self) -> bool:
        return self._data.empty

    # ── Inspection API ─────────────────────────────────────────────

    @property
    def removed(self) -> Dict[str, pd.DataFrame]:
        return dict(self._removed)

    @property
    def duplicates(self) -> pd.DataFrame:
        return self._removed.get("deduplicate", pd.DataFrame())

    def find_duplicates(
        self, fuzzy: bool = True, threshold: float = 85.0, subset: Optional[List[str]] = None
    ) -> pd.DataFrame:
        df = self._data
        if df.empty:
            return pd.DataFrame()
        cols = subset or df.columns.tolist()
        if fuzzy:
            try:
                import importlib.util

                RAPIDFUZZ_AVAILABLE = importlib.util.find_spec("rapidfuzz") is not None
            except (ImportError, AttributeError):
                RAPIDFUZZ_AVAILABLE = False
            if RAPIDFUZZ_AVAILABLE:
                from src.normalization.base import is_text_dtype
                from src.normalization.deduplication import fuzzy_deduplicate

                all_dupes = pd.Series(False, index=df.index)
                for col in cols:
                    if col in df.columns and is_text_dtype(df[col].dtype):
                        values = df[col].astype(str).tolist()
                        mapping = fuzzy_deduplicate(values, threshold)
                        dupe_vals = {orig for orig, canon in mapping if orig != canon}
                        all_dupes |= df[col].astype(str).isin(dupe_vals)
                return df[all_dupes].copy()
        from src.normalization.deduplication import normalize_key

        keys = df[cols].apply(lambda row: "".join(normalize_key(str(x)) for x in row), axis=1)
        dupe_mask = keys.duplicated(keep=False)
        return df[dupe_mask].copy()

    def suspicious(self) -> pd.DataFrame:
        if "_dq_status" not in self._data.columns:
            return pd.DataFrame()
        mask = self._data["_dq_status"].isin(("warn", "fail"))
        return self._data[mask].copy()

    def remove_rows(self, indices: Union[int, List[int]]) -> Document:
        if isinstance(indices, int):
            indices = [indices]
        indices = [i for i in indices if 0 <= i < len(self._data)]
        keep = self._data.index.difference(self._data.iloc[indices].index)
        new_doc = Document(self._data.loc[keep].reset_index(drop=True), metadata=self._metadata)
        new_doc._removed = dict(self._removed)
        return new_doc

    def keep_rows(self, func: Callable[[pd.Series], bool]) -> Document:
        mask = self._data.apply(func, axis=1)
        new_doc = Document(self._data[mask].reset_index(drop=True), metadata=self._metadata)
        new_doc._removed = dict(self._removed)
        return new_doc

    # ── Pipeline Integration ───────────────────────────────────────

    def transform(
        self,
        func: Callable[[pd.DataFrame], pd.DataFrame],
        stage_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Document:
        before = len(self._data)
        logger.info("Pipeline stage '%s' (%d rows)", stage_name, before)
        result = func(self._data.copy())
        if not isinstance(result, pd.DataFrame):
            raise TypeError(f"Stage '{stage_name}' must return a DataFrame, got {type(result)}")
        self._data = result
        self._metadata.add_step(
            ProcessingStep(
                name=stage_name,
                params=params or {},
                rows_before=before,
                rows_after=len(result),
            )
        )
        return self

    # ── Convenience Methods ────────────────────────────────────────

    def normalize(self) -> Document:
        return self.run_pipeline(["normalize"])

    def clean(self) -> Document:
        return self.run_pipeline(["clean"])

    def deduplicate(self, threshold: float = 85.0, fuzzy: bool = True, subset: Optional[List[str]] = None) -> Document:
        from src.normalization.pipeline import Pipeline
        from src.normalization.stages import DeduplicateStage

        return Pipeline([DeduplicateStage(threshold=threshold, fuzzy=fuzzy, subset=subset)]).run(self)

    def translate(
        self,
        target: str = "en",
        source: Optional[str] = None,
        columns: Optional[List[str]] = None,
    ) -> Document:
        from src.normalization.pipeline import Pipeline
        from src.normalization.stages import TranslateStage

        return Pipeline([TranslateStage(target=target, source=source, columns=columns)]).run(self)

    def enrich(self, **rules: Any) -> Document:
        from src.normalization.pipeline import Pipeline
        from src.normalization.stages import EnrichStage

        return Pipeline([EnrichStage(rules=rules)]).run(self)

    def validate(self, **kwargs: Any) -> Document:
        from src.dq import DQStage
        from src.normalization.pipeline import Pipeline

        return Pipeline([DQStage(**kwargs)]).run(self)

    def quality_report(self) -> dict:
        from src.dq import DQService

        report = DQService().quality_report(self._data)
        if self._metadata.quality_metrics:
            report["quality_metrics"] = self._metadata.quality_metrics
        return report

    @property
    def quality_metrics(self) -> dict:
        return dict(self._metadata.quality_metrics)

    # ── Pipeline Runner ────────────────────────────────────────────

    def run_pipeline(self, stages: Optional[List[str]] = None) -> Document:
        from src.dq import DQStage
        from src.normalization.pipeline import FULL_PIPELINE, Pipeline
        from src.normalization.stages import (
            CleanStage,
            DeduplicateStage,
            EnrichStage,
            ExportStage,
            ExtractStage,
            FormDetectStage,
            IngestStage,
            NormalizeStage,
            TranslateStage,
        )

        stage_map = {
            "ingest": IngestStage,
            "form_detect": FormDetectStage,
            "extract": ExtractStage,
            "normalize": NormalizeStage,
            "clean": CleanStage,
            "deduplicate": DeduplicateStage,
            "translate": TranslateStage,
            "enrich": EnrichStage,
            "dq": DQStage,
            "export": ExportStage,
        }

        if stages is None:
            stages = FULL_PIPELINE

        pipeline = Pipeline()
        for name in stages:
            cls = stage_map.get(name)
            if cls:
                pipeline.add(cls())

        return pipeline.run(self)

    # ── Infrastructure API ─────────────────────────────────────────

    @staticmethod
    def setup_logging(base_dir: Union[str, Path] = ".") -> None:
        from src.core.logging_config import setup_logging as _setup

        _setup(Path(base_dir))

    @staticmethod
    def list_exporters() -> List[str]:
        from src.exporters.registry import list_exporters as _list

        return _list()

    # ── Terminal Operations ────────────────────────────────────────

    def export(
        self,
        fmt: str,
        output_path: Optional[Union[str, Path]] = None,
        **kwargs: Any,
    ) -> Union[bytes, Path]:
        from src.exporters.registry import get_exporter

        fmt = fmt.lower().lstrip(".")
        exporter = get_exporter(fmt)

        path = Path(output_path) if output_path else None
        result = exporter.export(self._data, output_path=path, **kwargs)
        self._last_export_result = result

        if result.path:
            logger.info("Exported to %s", result.path)
            return result.path
        return result.data or b""

    def preview(self, rows: int = 10, show_meta: bool = True) -> str:
        from src.visualization import render_dataframe, render_metadata

        parts: List[str] = []
        if show_meta:
            parts.append(render_metadata(self._metadata))
        parts.append(render_dataframe(self._data, max_rows=rows))
        return "\n".join(parts)

    def report(self, validation_errors: Optional[pd.DataFrame] = None) -> str:
        from src.visualization import generate_report

        return generate_report(self._metadata, self._data, validation_errors=validation_errors)

    def diff(self, other: Document) -> str:
        from src.visualization import render_diff

        return render_diff(self._data, other._data)

    def head(self, n: int = 5) -> pd.DataFrame:
        return self._data.head(n)

    def to_pandas(self) -> pd.DataFrame:
        return self._data.copy()

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"Document(rows={len(self._data)}, cols={len(self._data.columns)}, source={self._metadata.source})"
