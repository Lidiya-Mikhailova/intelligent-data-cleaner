import json

import pandas as pd
import pytest

from src.core.cleaner import IntelligentDataCleaner, OutputFormats


@pytest.fixture
def tmp_project(tmp_path):
    (tmp_path / "bronze").mkdir()
    (tmp_path / "output").mkdir()
    (tmp_path / "fonts" / "dejavu_sans").mkdir(parents=True)
    return tmp_path


def test_output_formats_from_iter_all():
    formats = OutputFormats.from_iter(None)
    assert formats.csv is True
    assert formats.json is True
    assert formats.excel is True


def test_output_formats_from_iter_specific():
    formats = OutputFormats.from_iter(["csv", "json"])
    assert formats.csv is True
    assert formats.json is True
    assert formats.excel is False
    assert formats.pdf is False


def test_process_csv(tmp_project):
    csv_file = tmp_project / "bronze" / "test.csv"
    csv_file.write_text(
        "ID,Name,Age,Email,Address,Notes\n"
        "1,John,30,john@example.com,123 Main St,Test\n"
        "2,Jane,25,jane@example.com,456 Oak Ave,Test2\n"
    )

    cleaner = IntelligentDataCleaner(base_dir=tmp_project)
    fmt = OutputFormats(csv=True, json=False, excel=False, txt=False, pdf=False, safe_csv=False, jsonl=False)
    generated = cleaner.process_file(csv_file, formats=fmt)

    assert len(generated) >= 1
    csv_files = [p for p in generated if p.suffix == ".csv"]
    assert len(csv_files) == 1

    df = pd.read_csv(csv_files[0], sep=";")
    assert len(df) >= 2


def test_process_json(tmp_project):
    json_file = tmp_project / "bronze" / "test.json"
    json_file.write_text(
        json.dumps(
            [
                {
                    "ID": 1,
                    "Name": "John",
                    "Age": 30,
                    "Email": "john@example.com",
                    "Address": "123 Main St",
                    "Notes": "Test",
                },
                {
                    "ID": 2,
                    "Name": "Jane",
                    "Age": 25,
                    "Email": "jane@example.com",
                    "Address": "456 Oak Ave",
                    "Notes": "Test2",
                },
            ]
        )
    )

    cleaner = IntelligentDataCleaner(base_dir=tmp_project)
    fmt = OutputFormats(json=True, csv=False, excel=False, txt=False, pdf=False, safe_csv=False, jsonl=False)
    generated = cleaner.process_file(json_file, formats=fmt)

    assert len(generated) >= 1
    json_files = [p for p in generated if p.suffix == ".json"]
    assert len(json_files) == 1

    data = json.loads(json_files[0].read_text())
    assert len(data) >= 2


def test_process_unsupported_file(tmp_project):
    unsupported = tmp_project / "bronze" / "test.xml"
    unsupported.write_text("<root/>")

    cleaner = IntelligentDataCleaner(base_dir=tmp_project)
    generated = cleaner.process_file(unsupported)

    assert generated == []
