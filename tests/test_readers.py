import json
import zipfile

import pytest

from src.io.readers import (
    _detect_separator,
    _parse_kv_lines,
    _prepare_csv_text,
    load_csv_chunks,
    read_json_chunks,
    read_pdf_chunks,
    read_txt_chunks,
    read_zip_chunks,
)

# Separator detection


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("a|b|c", "|"),
        ("a,b,c", ","),
        ("a;b;c", ";"),
        ("a\tb\tc", "\t"),
        ("single", None),
    ],
)
def test_detect_separator(header, expected):
    assert _detect_separator(header) == expected


# CSV text preprocessing


def test_prepare_csv_text_strips_outer_quotes():
    text = '"Name,Age"\n"Alice",30\n'
    cleaned, sep = _prepare_csv_text(path_with(text))
    assert sep == ","
    assert cleaned.splitlines()[0] == "Name,Age"


def test_prepare_csv_text_normalizes_dirty_separators():
    text = "Name,Age\nJohn>30\nBob;25\n"
    cleaned, sep = _prepare_csv_text(path_with(text))
    assert sep == ","
    lines = cleaned.splitlines()
    assert lines[1] == "John,30"
    assert lines[2] == "Bob,25"


def test_prepare_csv_text_keeps_pipe():
    text = "Name|Age\nJohn|30\n"
    cleaned, sep = _prepare_csv_text(path_with(text))
    assert sep == "|"
    assert "|" in cleaned.splitlines()[1]


def test_prepare_csv_text_empty():
    assert _prepare_csv_text(path_with("")) == ("", None)


# CSV reading


def _path(tmp_path, text, name="data.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def path_with(text, name="data.csv"):
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp())
    p = tmp / name
    p.write_text(text, encoding="utf-8")
    return p


def test_load_csv_chunks_basic(tmp_path):
    p = _path(tmp_path, "Name,Age\nAlice,30\nBob,25\n")
    chunks = list(load_csv_chunks(p))
    assert len(chunks) == 1
    assert list(chunks[0].columns) == ["Name", "Age"]
    assert chunks[0].iloc[0]["Name"] == "Alice"


def test_load_csv_chunks_splits_by_chunksize(tmp_path):
    rows = "\n".join(f"r{i},{i}" for i in range(5))
    p = _path(tmp_path, "Name,Age\n" + rows + "\n")
    chunks = list(load_csv_chunks(p, chunksize=2))
    assert len(chunks) == 3
    assert sum(len(c) for c in chunks) == 5


def test_load_csv_chunks_detects_pipe(tmp_path):
    p = _path(tmp_path, "Name|Age\nAlice|30\n")
    chunks = list(load_csv_chunks(p))
    assert chunks[0].iloc[0]["Name"] == "Alice"


def test_load_csv_chunks_strips_whitespace_and_nan(tmp_path):
    p = _path(tmp_path, "Name,Age\n  Alice ,30\n,25\n")
    chunk = list(load_csv_chunks(p))[0]
    assert chunk.iloc[0]["Name"] == "Alice"
    assert chunk.iloc[1]["Name"] == ""


def test_load_csv_chunks_empty_file(tmp_path):
    p = _path(tmp_path, "")
    assert list(load_csv_chunks(p)) == []


# TXT reading


def test_read_txt_chunks_csv_style(tmp_path):
    p = _path(tmp_path, "Name,Age\nAlice,30\nBob,25\n", name="data.txt")
    chunks = list(read_txt_chunks(p))
    assert len(chunks) == 1
    assert list(chunks[0].columns) == ["Name", "Age"]
    assert len(chunks[0]) == 2


def test_parse_kv_lines_basic():
    df = _parse_kv_lines(["Founded: 1892", "CEO: James Quincey", "Website = https://x"])
    fields = set(df["Field"].astype(str))
    assert "Founded" in fields
    assert "CEO" in fields
    assert "Website" in fields
    assert df[df["Field"] == "Founded"].iloc[0]["Value"] == "1892"


def test_parse_kv_lines_multiline_values():
    df = _parse_kv_lines(["Name: John", "line two of name", "Age: 30"])
    name_val = df[df["Field"] == "Name"].iloc[0]["Value"]
    assert name_val == "John line two of name"


def test_parse_kv_lines_free_text():
    df = _parse_kv_lines(["hello plain text", "Name: Alice"])
    assert "Text" in set(df["Field"].astype(str))
    assert "Name" in set(df["Field"].astype(str))


def test_parse_kv_lines_empty():
    df = _parse_kv_lines([])
    assert list(df.columns) == ["Field", "Value", "SourceLine"]
    assert df.empty


def test_read_txt_chunks_kv_style(tmp_path):
    p = _path(tmp_path, "Founded: 1892\nCEO - James Quincey\n", name="data.txt")
    df = list(read_txt_chunks(p))[0]
    assert "Founded" in set(df["Field"].astype(str))


def test_read_txt_chunks_empty(tmp_path):
    p = _path(tmp_path, "", name="data.txt")
    df = list(read_txt_chunks(p))[0]
    assert df.empty


# JSON reading


def test_read_json_chunks_array(tmp_path):
    p = tmp_path / "data.json"
    p.write_text(json.dumps([{"Name": "Alice"}, {"Name": "Bob"}]), encoding="utf-8")
    chunks = list(read_json_chunks(p))
    assert len(chunks) == 1
    assert chunks[0]["Name"].tolist() == ["Alice", "Bob"]


def test_read_json_chunks_jsonl(tmp_path):
    p = tmp_path / "data.jsonl"
    p.write_text('{"Name": "Alice"}\n{"Name": "Bob"}\n', encoding="utf-8")
    chunks = list(read_json_chunks(p))
    assert chunks[0]["Name"].tolist() == ["Alice", "Bob"]


def test_read_json_chunks_jsonl_chunksize(tmp_path):
    p = tmp_path / "data.jsonl"
    p.write_text("".join(f'{{"i": {i}}}\n' for i in range(5)), encoding="utf-8")
    chunks = list(read_json_chunks(p, chunksize=2))
    assert len(chunks) >= 2
    assert sum(len(c) for c in chunks) == 5


# PDF reading


def test_read_pdf_chunks(tmp_path):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 5, "Name: John Doe")
    pdf.ln()
    pdf.cell(0, 5, "Age: 30")
    out = tmp_path / "doc.pdf"
    pdf.output(str(out))

    chunks = list(read_pdf_chunks(out))
    assert len(chunks) == 1
    fields = set(chunks[0]["Field"].astype(str))
    assert "Name" in fields
    assert "Age" in fields


# ZIP reading


def test_read_zip_chunks_csv_and_jsonl(tmp_path):
    csv_p = _path(tmp_path, "Name,Age\nAlice,30\n")
    jsonl_p = tmp_path / "data.jsonl"
    jsonl_p.write_text('{"Name": "Bob"}\n', encoding="utf-8")
    zip_p = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zip_p, "w") as z:
        z.write(csv_p, arcname="inner.csv")
        z.write(jsonl_p, arcname="inner.jsonl")
    chunks = list(read_zip_chunks(zip_p))
    assert len(chunks) == 2
    assert any("Alice" in str(c.values) for c in chunks)
    assert any("Bob" in str(c.values) for c in chunks)


def test_read_zip_chunks_ignores_unsupported(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("plain text file\n", encoding="utf-8")
    zip_p = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zip_p, "w") as z:
        z.write(p, arcname="notes.xyz")
    assert list(read_zip_chunks(zip_p)) == []
