import pandas as pd
import pytest

from src.core.cleaner import IntelligentDataCleaner, OutputFormats
from src.database import load_stage_result


@pytest.fixture
def tmp_project(tmp_path):
    (tmp_path / "bronze").mkdir()
    (tmp_path / "output").mkdir()
    (tmp_path / "fonts" / "dejavu_sans").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def valid_csv(tmp_project):
    csv_file = tmp_project / "bronze" / "test.csv"
    csv_file.write_text(
        "ID,Name,Age,Email,Address,Notes\n"
        "1,John,30,john@example.com,123 Main St,Test\n"
        "2,Jane,25,jane@example.com,456 Oak Ave,Test2\n"
    )
    return csv_file


@pytest.fixture
def mixed_csv(tmp_project):
    """CSV with both valid and invalid records."""
    csv_file = tmp_project / "mixed.csv"
    csv_file.write_text(
        "ID,Name,Age,Email,Address,Notes\n"
        "1,John,30,john@example.com,123 Main St,Test\n"
        "2,,25,jane@example.com,456 Oak Ave,Test2\n"
        "3,Jane,200,jane@example.com,456 Oak Ave,Test2\n"
    )
    return csv_file


def test_replay_from_silver(tmp_project, valid_csv):
    fmt = OutputFormats(csv=True, json=False, excel=False, txt=False, pdf=False, safe_csv=False, jsonl=False)
    cleaner = IntelligentDataCleaner(base_dir=tmp_project)
    cleaner.process_file(valid_csv, formats=fmt)

    paths = cleaner.replay_from_silver(str(valid_csv), formats=fmt)
    assert len(paths) >= 1
    csv_files = [p for p in paths if p.suffix == ".csv"]
    assert len(csv_files) == 1
    df = pd.read_csv(csv_files[0], sep=";")
    assert len(df) >= 2


def test_replay_from_silver_empty(tmp_project):
    fmt = OutputFormats(csv=True, json=False, excel=False, txt=False, pdf=False, safe_csv=False, jsonl=False)
    cleaner = IntelligentDataCleaner(base_dir=tmp_project)
    paths = cleaner.replay_from_silver("nonexistent", formats=fmt)
    assert paths == []


def test_reprocess_invalid(tmp_project, mixed_csv):
    fmt = OutputFormats(csv=True, json=False, excel=False, txt=False, pdf=False, safe_csv=False, jsonl=False)
    cleaner = IntelligentDataCleaner(base_dir=tmp_project)
    cleaner.process_file(mixed_csv, formats=fmt)

    paths = cleaner.reprocess_invalid(str(mixed_csv), formats=fmt)
    assert isinstance(paths, list)


def test_reprocess_invalid_no_data(tmp_project):
    fmt = OutputFormats(csv=True, json=False, excel=False, txt=False, pdf=False, safe_csv=False, jsonl=False)
    cleaner = IntelligentDataCleaner(base_dir=tmp_project)
    paths = cleaner.reprocess_invalid("nonexistent", formats=fmt)
    assert paths == []


def test_replay_stage(tmp_project, valid_csv):
    fmt = OutputFormats(csv=True, json=False, excel=False, txt=False, pdf=False, safe_csv=False, jsonl=False)
    cleaner = IntelligentDataCleaner(base_dir=tmp_project)
    cleaner.process_file(valid_csv, formats=fmt)

    paths = cleaner.replay_stage(str(valid_csv), "normalize", formats=fmt)
    assert len(paths) >= 1
    csv_files = [p for p in paths if p.suffix == ".csv"]
    assert len(csv_files) == 1
    df = pd.read_csv(csv_files[0], sep=";")
    assert len(df) >= 2


def test_replay_stage_nonexistent(tmp_project):
    fmt = OutputFormats(csv=True, json=False, excel=False, txt=False, pdf=False, safe_csv=False, jsonl=False)
    cleaner = IntelligentDataCleaner(base_dir=tmp_project)
    paths = cleaner.replay_stage("nonexistent", "normalize", formats=fmt)
    assert paths == []


def test_replay_stage_checkpoint_persisted(tmp_project, valid_csv):
    fmt = OutputFormats(csv=True, json=False, excel=False, txt=False, pdf=False, safe_csv=False, jsonl=False)
    cleaner = IntelligentDataCleaner(base_dir=tmp_project)
    cleaner.process_file(valid_csv, formats=fmt)

    stage_df = load_stage_result(cleaner.conn, "normalize", str(valid_csv))
    assert stage_df is not None
    assert len(stage_df) >= 2

    stage_df = load_stage_result(cleaner.conn, "clean", str(valid_csv))
    assert stage_df is not None
    assert len(stage_df) >= 2

    stage_df = load_stage_result(cleaner.conn, "deduplicate", str(valid_csv))
    assert stage_df is not None
    assert len(stage_df) >= 2


def test_rebuild_pipeline(tmp_project, valid_csv):
    fmt = OutputFormats(csv=True, json=False, excel=False, txt=False, pdf=False, safe_csv=False, jsonl=False)
    cleaner = IntelligentDataCleaner(base_dir=tmp_project)
    cleaner.process_file(valid_csv, formats=fmt)

    paths = cleaner.rebuild_pipeline(str(valid_csv), formats=fmt)
    assert len(paths) >= 1
    csv_files = [p for p in paths if p.suffix == ".csv"]
    assert len(csv_files) == 1
    df = pd.read_csv(csv_files[0], sep=";")
    assert len(df) >= 2


def test_rebuild_pipeline_empty_bronze(tmp_project):
    fmt = OutputFormats(csv=True, json=False, excel=False, txt=False, pdf=False, safe_csv=False, jsonl=False)
    cleaner = IntelligentDataCleaner(base_dir=tmp_project)
    paths = cleaner.rebuild_pipeline("nonexistent", formats=fmt)
    assert paths == []
