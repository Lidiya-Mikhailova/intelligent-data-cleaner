import pandas as pd
import pytest

from src.document import Document
from src.normalization.base import ProcessingStage
from src.normalization.pipeline import FULL_PIPELINE, Pipeline, _get_default_stages


class _FailingStage(ProcessingStage):
    name = "fail"

    def process(self, doc):
        raise RuntimeError("boom")


class _IdentityStage(ProcessingStage):
    name = "identity"

    def process(self, doc):
        return doc


class _TransformStage(ProcessingStage):
    name = "transform_stage"

    def process(self, doc):
        return doc.transform(lambda df: df.assign(extra=1), "transform_stage")


def _doc():
    return Document(pd.DataFrame({"A": [1, 2, 3]}))


def test_add_returns_self():
    p = Pipeline()
    assert p.add(_IdentityStage()) is p


def test_stages_returns_copy():
    p = Pipeline([_IdentityStage()])
    stages = p.stages
    stages.clear()
    assert len(p.stages) == 1


def test_run_passes_through_doc():
    doc = _doc()
    result = Pipeline([_IdentityStage(), _TransformStage()]).run(doc)
    assert result.data["extra"].tolist() == [1, 1, 1]


def test_run_re_raises_stage_error():
    doc = _doc()
    with pytest.raises(RuntimeError):
        Pipeline([_FailingStage()]).run(doc)


def test_run_empty_pipeline():
    doc = _doc()
    assert Pipeline().run(doc) is doc


def test_from_names_builds_stages():
    pipeline = Pipeline.from_names(["ingest", "clean", "export"])
    assert [s.name for s in pipeline.stages] == ["ingest", "clean", "export"]


def test_from_names_skips_unknown():
    pipeline = Pipeline.from_names(["ingest", "nope", "clean"])
    assert [s.name for s in pipeline.stages] == ["ingest", "clean"]


def test_full_pipeline_names():
    assert FULL_PIPELINE == [
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


def test_default_stages_registry():
    stages = _get_default_stages()
    assert set(stages) == set(FULL_PIPELINE)
