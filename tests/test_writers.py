import json
import zipfile

import pandas as pd

from src.io.writers import (
    MAX_COL_WIDTH,
    _align,
    _col_widths,
    _display_width,
    _pad,
    pdf_to_bytes,
    save_csv,
    save_csv_safe,
    save_excel,
    save_json,
    save_jsonl,
    save_pdf,
    save_txt,
    save_zip,
)


def _df():
    return pd.DataFrame({"Name": ["Alice", "Bob"], "Age": [30, 25]})


# Display helpers


def test_display_width_ascii():
    assert _display_width("Name") == 4


def test_display_width_cjk():
    assert _display_width("姓名") == 4


def test_pad_left_align_pads():
    assert _pad("ab", 4) == "ab  "


def test_pad_right_align_pads():
    assert _pad("ab", 4, "right") == "  ab"


def test_pad_exact_width():
    assert _pad("abcd", 4) == "abcd"


def test_pad_truncates_with_ellipsis():
    assert _pad("abcdef", 4) == "abc…"


def test_pad_truncates_cjk():
    out = _pad("姓名一二", 4)
    assert _display_width(out) <= 4
    assert out.endswith("…")


def test_col_widths_min_and_max():
    df = pd.DataFrame({"A": ["x"], "B": ["y" * 200]})
    widths = _col_widths(df)
    assert widths[0] >= len("A") + 2
    assert widths[1] == MAX_COL_WIDTH


def test_align_numeric_right():
    assert _align(30, 5, "Age") == "   30"


def test_align_text_left():
    assert _align("Alice", 7, "Name") == "Alice  "


# save_* functions


def test_save_csv(tmp_path):
    out = tmp_path / "out.csv"
    save_csv(_df(), out)
    assert pd.read_csv(out)["Name"].tolist() == ["Alice", "Bob"]


def test_save_csv_safe(tmp_path):
    out = tmp_path / "out.safe"
    save_csv_safe(_df(), out)
    text = out.read_text(encoding="utf-8")
    assert text.startswith("┌")
    assert "Name" in text
    assert "└" in text


def test_save_excel(tmp_path):
    out = tmp_path / "out.xlsx"
    save_excel(_df(), out)
    df = pd.read_excel(out, sheet_name="CleanData")
    assert df["Name"].tolist() == ["Alice", "Bob"]


def test_save_txt(tmp_path):
    out = tmp_path / "out.txt"
    save_txt(_df(), out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert "Name" in lines[0]
    assert "═" in lines[1]
    assert "Alice" in "\n".join(lines)


def test_save_json_roundtrip(tmp_path):
    out = tmp_path / "out.json"
    save_json(_df(), out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data[0] == {"Name": "Alice", "Age": 30}


def test_save_jsonl_roundtrip(tmp_path):
    out = tmp_path / "out.jsonl"
    save_jsonl(_df(), out)
    lines = [json.loads(ln) for ln in out.read_text(encoding="utf-8").splitlines() if ln]
    assert lines[1] == {"Name": "Bob", "Age": 25}


def test_save_pdf(tmp_path):
    out = tmp_path / "out.pdf"
    save_pdf(_df(), out)
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    assert b"DejaVu" in data


def test_pdf_to_bytes():
    data = pdf_to_bytes(_df())
    assert isinstance(data, bytes)
    assert data.startswith(b"%PDF")


def test_pdf_to_bytes_with_font_path(tmp_path):
    data = pdf_to_bytes(_df(), font_path=tmp_path / "missing.ttf")
    assert data.startswith(b"%PDF")


def test_save_zip(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.json"
    a.write_text("x\n", encoding="utf-8")
    b.write_text("{}", encoding="utf-8")
    out = tmp_path / "bundle.zip"
    result = save_zip([a, b], out)
    assert result == out
    with zipfile.ZipFile(out) as zf:
        assert set(zf.namelist()) == {"a.csv", "b.json"}
