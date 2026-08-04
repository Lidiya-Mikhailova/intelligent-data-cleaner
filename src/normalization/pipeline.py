from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional

from src.normalization.base import ProcessingStage

if TYPE_CHECKING:
    from src.document import Document

logger = logging.getLogger(__name__)

FULL_PIPELINE = [
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


class Pipeline:
    def __init__(self, stages: Optional[List[ProcessingStage]] = None):
        self._stages: List[ProcessingStage] = stages or []

    def add(self, stage: ProcessingStage) -> Pipeline:
        self._stages.append(stage)
        return self

    @property
    def stages(self) -> List[ProcessingStage]:
        return list(self._stages)

    def run(self, doc: Document) -> Document:
        for stage in self._stages:
            logger.info("Running pipeline stage: %s", stage.name)
            try:
                doc = stage.process(doc)
            except Exception as e:
                logger.error("Pipeline stage %s failed: %s", stage.name, e)
                raise
        return doc

    @classmethod
    def from_names(cls, names: List[str]) -> Pipeline:
        stage_map = _get_default_stages()
        pipeline = cls()
        for name in names:
            cls_ = stage_map.get(name)
            if cls_:
                pipeline.add(cls_())
        return pipeline


def _get_default_stages() -> Dict[str, type]:
    from src.dq import DQStage
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

    return {
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
