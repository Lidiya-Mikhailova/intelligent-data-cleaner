from __future__ import annotations

from pathlib import Path
from typing import Generator, List, Tuple, Optional

import pandas as pd


def load_csv_chunks(path: Path, chunksize: int = 50_000) -> Generator[pd.DataFrame, None, None]:
    """
    Read CSV in chunks. Use a stable separator strategy.
    If you want auto-detection, keep sep=None, but for reliability prefer comma.
    """
    for chunk in pd.read_csv(
        path,
        sep=None,               # auto-detect; ok for real CSV
        engine="python",
        dtype=str,
        chunksize=chunksize,
        on_bad_lines="skip",
    ):
        yield chunk.fillna("")


def _parse_kv_lines(lines: List[str]) -> pd.DataFrame:
    """
    Parse semi-structured text like:
    Founded: 1892
    CEO - James Quincey
    Website = https://...
    Supports multiline values: lines after a key are appended until next key.
    """
    import re

    kv_re = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 _/\-\.\(\)]{0,60})\s*[:=\-]\s*(.+?)\s*$")

    rows: List[Tuple[str, str, str]] = []
    current_key: Optional[str] = None
    current_val: List[str] = []
    current_src: List[str] = []

    def flush():
        nonlocal current_key, current_val, current_src, rows
        if current_key and current_val:
            rows.append(
                (current_key.strip(), " ".join(v.strip() for v in current_val if v.strip()).strip(), " | ".join(s.strip() for s in current_src if s.strip()).strip())
            )
        current_key = None
        current_val = []
        current_src = []

    for raw in lines:
        s = (raw or "").strip()
        if not s:
            continue

        m = kv_re.match(s)
        if m:
            flush()
            current_key = m.group(1)
            current_val = [m.group(2)]
            current_src = [s]
            continue

        # not a KV line, treat as continuation if we already have a key
        if current_key:
            current_val.append(s)
            current_src.append(s)
        else:
            # free text line -> keep as Text field
            rows.append(("Text", s, s))

    flush()

    if not rows:
        return pd.DataFrame(columns=["Field", "Value", "SourceLine"])

    df = pd.DataFrame(rows, columns=["Field", "Value", "SourceLine"])
    return df


def read_txt_chunks(path: Path, chunksize: int = 50_000) -> Generator[pd.DataFrame, None, None]:
    """
    Read a TXT as text and convert to a structured DataFrame:
    Field | Value | SourceLine
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    df = _parse_kv_lines(lines)

    # chunk it (optional)
    if len(df) <= chunksize:
        yield df.fillna("")
        return

    start = 0
    while start < len(df):
        yield df.iloc[start : start + chunksize].copy().fillna("")
        start += chunksize


def read_pdf_chunks(path: Path) -> Generator[pd.DataFrame, None, None]:
    """
    Read PDF page-by-page and parse text into Field | Value.
    Works for text-based PDFs (not scanned).
    """
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [ln for ln in text.split("\n") if ln.strip()]
            if not lines:
                continue
            df = _parse_kv_lines(lines)
            if not df.empty:
                yield df.fillna("")


def read_json_chunks(path: Path, chunksize: int = 50_000) -> Generator[pd.DataFrame, None, None]:
    """
    Read JSON (.json) or JSON Lines (.jsonl).
    """
    suffix = path.suffix.lower()

    if suffix in {".jsonl", ".jsonlines"}:
        buf = []
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                buf.append(line)
                if len(buf) >= chunksize:
                    df = pd.read_json("\n".join(buf), lines=True, dtype=False)
                    yield df.fillna("").astype(str)
                    buf = []
        if buf:
            df = pd.read_json("\n".join(buf), lines=True, dtype=False)
            yield df.fillna("").astype(str)
        return

    raw = path.read_text(encoding="utf-8", errors="replace").lstrip()
    try:
        if raw.startswith("[") or raw.startswith("{"):
            df = pd.read_json(path, orient="records", dtype=False)
        else:
            df = pd.read_json(path, lines=True, dtype=False)
    except ValueError:
        df = pd.read_json(path, lines=True, dtype=False)

    yield df.fillna("").astype(str)