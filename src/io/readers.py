from __future__ import annotations

from pathlib import Path
from typing import Generator

import pandas as pd


def load_csv_chunks(path: Path, chunksize: int = 50_000) -> Generator[pd.DataFrame, None, None]:
    """
    Read CSV/TXT in chunks using pandas auto-separator detection.
    """
    for chunk in pd.read_csv(
        path,
        sep=None,
        engine="python",
        dtype=str,
        chunksize=chunksize,
        on_bad_lines="skip",
    ):
        yield chunk.fillna("")


def read_pdf_chunks(path: Path) -> Generator[pd.DataFrame, None, None]:
    """
    Read PDF page-by-page and convert to a DataFrame with a single 'Text' column.
    """
    import pdfplumber  # local import to keep base deps lighter

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = [ln for ln in text.split("\n") if ln.strip()]
            if lines:
                yield pd.DataFrame({"Text": lines})


def read_json_chunks(path: Path, chunksize: int = 50_000) -> Generator[pd.DataFrame, None, None]:
    """
    Read JSON (.json) or JSON Lines (.jsonl) and yield DataFrames.
    - .json  : expects list of objects (records) or dict-like JSON
    - .jsonl : one JSON object per line
    """
    suffix = path.suffix.lower()

    # JSONL: stream by lines (chunked)
    if suffix in {".jsonl", ".jsonlines"}:
        buf = []
        with path.open("r", encoding="utf-8") as f:
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

    # JSON: try to load full (usually not huge); if it's actually JSONL by mistake, fallback to lines=True
    raw = path.read_text(encoding="utf-8", errors="replace").lstrip()
    try:
        if raw.startswith("[") or raw.startswith("{"):
            df = pd.read_json(path, orient="records", dtype=False)
        else:
            # fallback
            df = pd.read_json(path, lines=True, dtype=False)
    except ValueError:
        df = pd.read_json(path, lines=True, dtype=False)

    # Normalize to strings and yield once
    yield df.fillna("").astype(str)