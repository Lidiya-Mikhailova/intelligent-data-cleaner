import io
import json

import pandas as pd
import pytest

from src.exporters.registry import (
    Exporter,
    ExportResult,
    _export_metadata,
    get_exporter,
    list_exporters,
    register_exporter,
)


def _df():
    return pd.DataFrame({"Name": ["Alice", "Bob"], "Age": [30, 25]})


ALL_FORMATS = ["csv", "json", "jsonl", "xlsx", "txt", "pdf", "parquet", "safe_csv"]


# Registry basics


def test_list_exporters():
    assert set(ALL_FORMATS).issubset(set(list_exporters()))


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_get_exporter_normalizes(fmt):
    assert get_exporter(fmt).format_name == fmt
    assert get_exporter(fmt.upper()).format_name == fmt
    assert get_exporter("." + fmt).format_name == fmt


def test_get_exporter_unknown_raises():
    with pytest.raises(ValueError, match="No exporter registered"):
        get_exporter("docx")


def test_register_exporter_custom():
    @register_exporter
    class CustomExporter(Exporter):
        format_name = "custom_xyz"

        def export(self, df, output_path=None, **kwargs):
            return ExportResult(format=self.format_name, data=b"custom")

    try:
        exporter = get_exporter("custom_xyz")
        res = exporter.export(_df())
        assert res.format == "custom_xyz"
        assert res.data == b"custom"
    finally:
        # restore registry so list_exporters stays stable
        from src.exporters.registry import _exporter_registry

        del _exporter_registry["custom_xyz"]


def test_exporter_suffix_property():
    assert get_exporter("csv").suffix == ".csv"


def test_export_metadata():
    meta = _export_metadata(_df(), compression="snappy")
    assert meta == {"rows": 2, "columns": 2, "compression": "snappy"}


# Individual exporters


def test_csv_exporter_roundtrip_bytes():
    res = get_exporter("csv").export(_df())
    assert res.format == "csv"
    df = pd.read_csv(io.BytesIO(res.data))
    assert df["Name"].tolist() == ["Alice", "Bob"]


def test_csv_exporter_writes_path(tmp_path):
    out = tmp_path / "out.csv"
    res = get_exporter("csv").export(_df(), output_path=out)
    assert res.path == out
    assert out.exists()
    assert pd.read_csv(out)["Name"].tolist() == ["Alice", "Bob"]


def test_json_exporter_roundtrip():
    res = get_exporter("json").export(_df())
    data = json.loads(res.data)
    assert data == [
        {"Name": "Alice", "Age": 30},
        {"Name": "Bob", "Age": 25},
    ]


def test_jsonl_exporter_lines():
    res = get_exporter("jsonl").export(_df())
    lines = [json.loads(ln) for ln in res.data.decode("utf-8").splitlines() if ln]
    assert lines[0]["Name"] == "Alice"
    assert lines[1]["Name"] == "Bob"


def test_excel_exporter_roundtrip():
    res = get_exporter("xlsx").export(_df())
    assert res.data[:2] == b"PK"
    df = pd.read_excel(io.BytesIO(res.data), sheet_name="Data")
    assert df["Name"].tolist() == ["Alice", "Bob"]


def test_txt_exporter_text():
    res = get_exporter("txt").export(_df())
    text = res.data.decode("utf-8")
    assert "Name" in text and "Age" in text
    assert "Alice" in text


def test_pdf_exporter_bytes():
    res = get_exporter("pdf").export(_df())
    assert res.data.startswith(b"%PDF")
    assert "font" not in res.metadata or res.metadata["font"] is False


def test_parquet_exporter_roundtrip():
    res = get_exporter("parquet").export(_df())
    df = pd.read_parquet(io.BytesIO(res.data))
    assert df["Age"].tolist() == [30, 25]
    assert res.metadata["compression"] == "snappy"


def test_parquet_exporter_writes_path(tmp_path):
    out = tmp_path / "out.parquet"
    res = get_exporter("parquet").export(_df(), output_path=out, compression="gzip")
    assert res.path == out
    assert out.exists()
    assert res.metadata["compression"] == "gzip"
    assert pd.read_parquet(out)["Name"].tolist() == ["Alice", "Bob"]


def test_safe_csv_exporter_writes_table(tmp_path):
    out = tmp_path / "out.safe"
    res = get_exporter("safe_csv").export(_df(), output_path=out)
    assert res.path == out
    text = out.read_text(encoding="utf-8")
    assert "┌" in text
    assert "Name" in text
