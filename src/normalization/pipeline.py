from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.normalization.base import ProcessingStage

if TYPE_CHECKING:
    from src.document import Document

logger = logging.getLogger(__name__)

FULL_PIPELINE = ["ingest", "extract", "normalize", "clean", "deduplicate", "translate", "enrich", "export"]


class Pipeline:
    def __init__(self, stages: Optional[List[ProcessingStage]] = None):
        self._stages: List[ProcessingStage] = stages or []

    def add(self, stage: ProcessingStage) -> Pipeline:
        self._stages.append(stage)
        return self

    def remove(self, name: str) -> Pipeline:
        self._stages = [s for s in self._stages if s.name != name]
        return self

    def insert(self, index: int, stage: ProcessingStage) -> Pipeline:
        self._stages.insert(index, stage)
        return self

    def clear(self) -> Pipeline:
        self._stages.clear()
        return self

    @property
    def stages(self) -> List[ProcessingStage]:
        return list(self._stages)

    @property
    def stage_names(self) -> List[str]:
        return [s.name for s in self._stages]

    def run(self, doc: Document) -> Document:
        for stage in self._stages:
            logger.info("Running pipeline stage: %s", stage.name)
            try:
                doc = stage.process(doc)
            except Exception as e:
                logger.error("Pipeline stage %s failed: %s", stage.name, e)
                raise
        return doc

    def run_with_checkpoints(
        self,
        doc: Document,
        conn: Any,
        run_id: int,
        source_file: str,
    ) -> Document:
        """Run pipeline stages and persist each stage's output to DuckDB.

        Each stage result is saved as ``stage_<stem>_<stage_name>``,
        enabling replay from any stage without re-running prior stages.
        """
        from src.database.pipeline_runs import save_stage_result

        for stage in self._stages:
            logger.info("Running pipeline stage (checkpoint): %s", stage.name)
            try:
                doc = stage.process(doc)
                save_stage_result(conn, stage.name, doc.data, source_file)
            except Exception as e:
                logger.error("Pipeline stage %s failed: %s", stage.name, e)
                raise
        return doc

    @classmethod
    def from_stage(
        cls,
        start_stage: str,
        stage_names: List[str],
    ) -> Pipeline:
        """Build a pipeline that runs stages *from* ``start_stage`` onward.

        Only stage names at or after ``start_stage`` in ``FULL_PIPELINE``
        order are included.  Useful for replaying a subset of the pipeline.
        """
        start_idx = FULL_PIPELINE.index(start_stage) if start_stage in FULL_PIPELINE else 0
        requested = set(stage_names)
        names = [s for s in FULL_PIPELINE[start_idx:] if s in requested]
        return cls.from_names(names)

    @classmethod
    def from_names(cls, names: List[str]) -> Pipeline:
        """Build a pipeline from a list of stage names (with default params)."""
        stage_map = _get_default_stages()
        pipeline = cls()
        for name in names:
            cls_ = stage_map.get(name)
            if cls_:
                pipeline.add(cls_())
        return pipeline

    def run_selected(self, doc: Document, names: List[str]) -> Document:
        for stage in self._stages:
            if stage.name in names:
                logger.info("Running selected stage: %s", stage.name)
                doc = stage.process(doc)
        return doc

    def to_config(self) -> List[Dict[str, Any]]:
        config = []
        for stage in self._stages:
            entry: Dict[str, Any] = {"name": stage.name}
            if hasattr(stage, "params"):
                entry["params"] = stage.params
            config.append(entry)
        return config

    @classmethod
    def from_config(cls, config: List[Dict[str, Any]]) -> Pipeline:
        pipeline = cls()
        stage_map = _get_default_stages()
        for entry in config:
            name = entry.get("name", "")
            stage_cls = stage_map.get(name)
            if stage_cls:
                params = entry.get("params", {})
                pipeline.add(stage_cls(**params))
        return pipeline


def _get_default_stages() -> Dict[str, type]:
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

    return {
        "ingest": IngestStage,
        "extract": ExtractStage,
        "normalize": NormalizeStage,
        "clean": CleanStage,
        "deduplicate": DeduplicateStage,
        "translate": TranslateStage,
        "enrich": EnrichStage,
        "export": ExportStage,
    }
