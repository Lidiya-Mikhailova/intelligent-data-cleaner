from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pandas as pd

from src.core.metadata import DocumentMetadata, ProcessingStep
from src.io.ocr import OCREngine

logger = logging.getLogger(__name__)

FULL_PIPELINE_STAGES = ["ingest", "extract", "normalize", "clean", "deduplicate", "translate", "enrich", "export"]


class Document:
    """Central abstraction for intelligent document processing.

    Factory methods:
        from_file, from_zip, from_text, from_dict, from_bytes, from_scan

    Chainable processing methods (return self):
        normalize, clean, deduplicate, translate, enrich, run_pipeline

    Terminal methods:
        export (returns bytes or Path), preview (returns str), report (returns str)
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
    def from_zip(cls, path: Union[str, Path]) -> Document:
        return cls.from_file(path)

    @classmethod
    def from_text(cls, text: str, **meta_kwargs) -> Document:
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

    @classmethod
    def from_scan(
        cls,
        path: Union[str, Path],
        engine: Optional[Union[str, OCREngine]] = None,
    ) -> Document:
        from src.normalization.pipeline import Pipeline
        from src.normalization.stages import ExtractStage, IngestStage

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return Pipeline([IngestStage(path=path, scan=True, engine=engine), ExtractStage()]).run(cls(pd.DataFrame()))

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

    # ── Pipeline Integration ───────────────────────────────────────

    def transform(
        self,
        func: Callable[[pd.DataFrame], pd.DataFrame],
        stage_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Document:
        """Apply a DataFrame transformation as a pipeline stage.

        Called by Pipeline stages and Document convenience methods.
        Records the step in metadata automatically.
        """
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

    # ── Medallion Pipeline (Bronze → Silver → Gold) ────────────────

    def process(self, base_dir: Union[str, Path] = ".", formats: Optional[List[str]] = None) -> List[Path]:
        """Run the full Medallion pipeline on this document's source file.

        Processes through Bronze (raw) → Silver (VALID/INVALID/QUARANTINE)
        → Gold (final) → Export. Requires a file-based document.
        """
        from src.core.cleaner import IntelligentDataCleaner

        source = self._metadata.source
        if not source or source.startswith("memory:"):
            raise RuntimeError(
                "Document.process() requires a file source (use Document.from_file() or Document.from_scan())"
            )
        fmt = self._make_formats(formats)
        with IntelligentDataCleaner(Path(base_dir)) as cleaner:
            return cleaner.process_file(Path(source), formats=fmt)

    # ── Batch Processing ───────────────────────────────────────────

    @classmethod
    def process_all(cls, base_dir: Union[str, Path] = ".", formats: Optional[List[str]] = None) -> List[Path]:
        """Process all supported files in the bronze/ directory."""
        from src.core.cleaner import IntelligentDataCleaner

        fmt = cls._make_formats(formats)
        with IntelligentDataCleaner(Path(base_dir)) as cleaner:
            return cleaner.process_all(fmt)

    # ── Replay Methods ─────────────────────────────────────────────

    def replay_from_silver(
        self,
        base_dir: Union[str, Path] = ".",
        formats: Optional[List[str]] = None,
    ) -> List[Path]:
        """Re-run pipeline from Silver layer on this document's source."""
        from src.core.cleaner import IntelligentDataCleaner

        fmt = self._make_formats(formats)
        with IntelligentDataCleaner(Path(base_dir)) as cleaner:
            return cleaner.replay_from_silver(self._metadata.source, formats=fmt)

    def reprocess_invalid(
        self,
        base_dir: Union[str, Path] = ".",
        formats: Optional[List[str]] = None,
    ) -> List[Path]:
        """Re-process invalid records from Silver layer."""
        from src.core.cleaner import IntelligentDataCleaner

        fmt = self._make_formats(formats)
        with IntelligentDataCleaner(Path(base_dir)) as cleaner:
            return cleaner.reprocess_invalid(self._metadata.source, formats=fmt)

    def replay_stage(
        self,
        stage_name: str,
        base_dir: Union[str, Path] = ".",
        formats: Optional[List[str]] = None,
    ) -> List[Path]:
        """Re-run pipeline from a specific stage checkpoint."""
        from src.core.cleaner import IntelligentDataCleaner

        fmt = self._make_formats(formats)
        with IntelligentDataCleaner(Path(base_dir)) as cleaner:
            return cleaner.replay_stage(self._metadata.source, stage_name, formats=fmt)

    def rebuild_pipeline(
        self,
        base_dir: Union[str, Path] = ".",
        formats: Optional[List[str]] = None,
    ) -> List[Path]:
        """Re-run pipeline from Bronze layer."""
        from src.core.cleaner import IntelligentDataCleaner

        fmt = self._make_formats(formats)
        with IntelligentDataCleaner(Path(base_dir)) as cleaner:
            return cleaner.rebuild_pipeline(self._metadata.source, formats=fmt)

    @staticmethod
    def _make_formats(formats: Optional[List[str]]):
        from src.core.cleaner import OutputFormats

        return OutputFormats.from_iter(formats)

    # ── Infrastructure API ─────────────────────────────────────────

    @staticmethod
    def setup_logging(base_dir: Union[str, Path] = ".") -> None:
        """Configure project-wide logging."""
        from src.core.logging_config import setup_logging as _setup

        _setup(Path(base_dir))

    @staticmethod
    def list_exporters() -> List[str]:
        """List all available export format names."""
        from src.exporters.registry import list_exporters as _list

        return _list()

    @classmethod
    def from_config(
        cls,
        config_path: Union[str, Path],
        override_input: Optional[str] = None,
    ) -> Document:
        """Create a Document by running a pipeline defined in a YAML/JSON config file."""
        from src.config.loader import run_from_config

        return run_from_config(Path(config_path), override_input=override_input)

    @classmethod
    def list_tables(
        cls,
        layer: str = "gold",
        base_dir: Union[str, Path] = ".",
    ) -> "pd.DataFrame":
        """List tables in a Medallion layer (bronze/silver/gold)."""
        from src.core.cleaner import IntelligentDataCleaner

        with IntelligentDataCleaner(Path(base_dir)) as cleaner:
            if layer == "gold":
                return cleaner.list_gold()
            if layer == "silver":
                from src.database import get_silver_tables

                return get_silver_tables(cleaner.conn)
            return cleaner.conn.execute("SELECT * FROM bronze_files ORDER BY ingested_at DESC").fetchdf()

    @classmethod
    def export_table(
        cls,
        table_name: str,
        base_dir: Union[str, Path] = ".",
        formats: Optional[List[str]] = None,
    ) -> List[Path]:
        """Export a gold table to files."""
        from src.core.export_service import export_data
        from src.database import get_db_path, init_db, read_table

        db_path = get_db_path(Path(base_dir))
        conn = init_db(db_path)
        output_dir = Path(base_dir) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        font_dir = Path(base_dir) / "fonts" / "dejavu_sans"
        try:
            df = read_table(conn, table_name)
            if df.empty:
                return []
            return export_data(df, output_dir, formats=formats, font_dir=font_dir, base_name=table_name)
        finally:
            conn.close()

    # ── Convenience Methods (delegate through Pipeline engine) ─────

    def normalize(self) -> Document:
        return self.run_pipeline(["normalize"])

    def clean(self) -> Document:
        return self.run_pipeline(["clean"])

    def deduplicate(self, threshold: float = 85.0, fuzzy: bool = True) -> Document:
        from src.normalization.pipeline import Pipeline
        from src.normalization.stages import DeduplicateStage

        return Pipeline([DeduplicateStage(threshold=threshold, fuzzy=fuzzy)]).run(self)

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

    # ── Pipeline Runner ────────────────────────────────────────────

    def run_pipeline(self, stages: Optional[List[str]] = None) -> Document:
        from src.normalization.pipeline import FULL_PIPELINE, Pipeline
        from src.normalization.stages import (
            CleanStage,
            DeduplicateStage,
            EnrichStage,
            ExportStage,
            ExtractStage,
            IngestStage,
            NormalizeStage,
            TranslateStage,
        )

        stage_map = {
            "ingest": IngestStage,
            "extract": ExtractStage,
            "normalize": NormalizeStage,
            "clean": CleanStage,
            "deduplicate": DeduplicateStage,
            "translate": TranslateStage,
            "enrich": EnrichStage,
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
        from src.visualization.render import render_dataframe, render_metadata

        parts: List[str] = []
        if show_meta:
            parts.append(render_metadata(self._metadata))
        parts.append(render_dataframe(self._data, max_rows=rows))
        return "\n".join(parts)

    def report(self, validation_errors: Optional[pd.DataFrame] = None) -> str:
        from src.visualization.reports import generate_report

        return generate_report(self._metadata, self._data, validation_errors=validation_errors)

    def diff(self, other: Document) -> str:
        from src.visualization.render import render_diff

        return render_diff(self._data, other._data)

    def head(self, n: int = 5) -> pd.DataFrame:
        return self._data.head(n)

    def to_pandas(self) -> pd.DataFrame:
        return self._data.copy()

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"Document(rows={len(self._data)}, cols={len(self._data.columns)}, source={self._metadata.source})"
