from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import Generator, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def _detect_separator(header: str) -> Optional[str]:
    candidates = [("|", "|"), (",", ","), (";", ";"), ("\t", "\t")]
    best = None
    best_count = 0
    for sep, char in candidates:
        count = header.count(char)
        if count > best_count:
            best_count = count
            best = sep
    return best


def _looks_like_csv(text: str) -> bool:
    """Detect if text content looks like CSV (comma/semicolon/tab/pipe separated with consistent columns)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False

    candidate_seps = [",", ";", "\t", "|"]
    candidate_lines = []
    for line in lines:
        sep_counts = [line.count(s) for s in candidate_seps]
        if max(sep_counts) > 0:
            candidate_lines.append(line)
        if len(candidate_lines) >= 10:
            break

    if len(candidate_lines) < 2:
        return False

    for sep in candidate_seps:
        counts = [line.count(sep) for line in candidate_lines]
        if all(c > 0 for c in counts) and max(counts) - min(counts) <= 3:
            return True
    return False


def _prepare_csv_text(path: Path) -> Tuple[str, Optional[str]]:
    """Read and pre-process CSV text: strip outer quotes, normalize separators.

    Returns ``(cleaned_text, detected_separator)``.
    Separator normalisation (``< > ; : |`` → ``,``) is only applied when the
    detected separator is ``,`` (or none).  Pipe-delimited files keep ``|``.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()
    if not lines:
        return "", None

    processed = []
    for line in lines:
        s = line.strip()
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"' and '"' not in s[1:-1]:
            s = s[1:-1]
        processed.append(s)

    sep = _detect_separator(processed[0])

    if sep == "," or sep is None:
        header = processed[0]
        n_cols = header.count(",") + 1
        for i in range(1, len(processed)):
            line = processed[i]
            if not line:
                continue
            if line.count(",") >= n_cols - 1:
                continue
            for ch in "<>;:|":
                line = line.replace(ch, ",")
            if line.count(",") < n_cols - 1 and "." in line:
                line = re.sub(r"(?<=\d)\.(?=[A-Za-z])", ",", line)
                line = re.sub(r"(?<=[A-Za-z])\.(?=\d)", ",", line)
            processed[i] = line

    return "\n".join(processed), sep


def load_csv_chunks(path: Path, chunksize: int = 50_000) -> Generator[pd.DataFrame, None, None]:
    """
    Read CSV in chunks. Pre-processes text to strip outer quotes from lines
    and normalizes common separator characters (``< > ; : |``) in dirty rows.
    Strips whitespace from column names and cell values.
    """
    text, detected_sep = _prepare_csv_text(path)
    if not text:
        return

    for chunk in pd.read_csv(
        io.StringIO(text),
        sep=detected_sep,
        engine="python",
        dtype=str,
        chunksize=chunksize,
        on_bad_lines="skip",
        skipinitialspace=True,
    ):
        chunk.columns = [c.strip() for c in chunk.columns]
        chunk = chunk.map(lambda x: x.strip() if isinstance(x, str) else x)
        yield chunk.fillna("")


def _parse_kv_lines(lines: List[str]) -> pd.DataFrame:
    """
    Parse semi-structured text like:
    Founded: 1892
    CEO - James Quincey
    Website = https://...
    Supports multiline values: lines after a key are appended until next key.
    """

    kv_re = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 _/\.\(\)]{0,60})\s*[:=]\s*(.+?)\s*$")

    rows: List[Tuple[str, str, str]] = []
    current_key: Optional[str] = None
    current_val: List[str] = []
    current_src: List[str] = []

    def flush():
        nonlocal current_key, current_val, current_src, rows
        if current_key and current_val:
            val = " ".join(v.strip() for v in current_val if v.strip()).strip()
            src = " | ".join(s.strip() for s in current_src if s.strip()).strip()
            rows.append((current_key.strip(), val, src))
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
    Read a TXT file. Auto-detects CSV-formatted TXT files and parses them as CSV.
    Otherwise treats as semi-structured text (Field | Value | SourceLine).
    """
    text = path.read_text(encoding="utf-8", errors="replace")

    if _looks_like_csv(text):
        import tempfile

        lines = text.splitlines()
        csv_lines = [line for line in lines if any(s in line for s in (",", ";", "\t", "|"))]
        if not csv_lines:
            yield pd.DataFrame()
            return

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as tmp:
            tmp.write("\n".join(csv_lines))
            tmp_path = Path(tmp.name)
        try:
            yield from load_csv_chunks(tmp_path, chunksize)
        finally:
            tmp_path.unlink()
        return

    lines = text.splitlines()
    df = _parse_kv_lines(lines)

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
    Works for text-based PDFs.
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


def read_zip_chunks(
    path: Path,
    chunksize: int = 50_000,
) -> Generator[pd.DataFrame, None, None]:
    """
    Extract supported files from a ZIP archive and yield DataFrames.
    Supported inner formats: .csv, .txt, .json, .jsonl, .jsonlines, .xlsx.
    """
    import tempfile
    import zipfile

    SUPPORTED = {".csv", ".txt", ".json", ".jsonl", ".jsonlines", ".xlsx"}

    with zipfile.ZipFile(path, "r") as zf:
        for entry in zf.namelist():
            ext = Path(entry).suffix.lower()
            if ext not in SUPPORTED:
                continue

            with tempfile.TemporaryDirectory() as tmpdir:
                zf.extract(entry, tmpdir)
                extracted = Path(tmpdir) / entry

                if ext == ".csv":
                    yield from load_csv_chunks(extracted, chunksize)
                elif ext == ".txt":
                    yield from read_txt_chunks(extracted, chunksize)
                elif ext == ".xlsx":
                    yield from read_excel_chunks(extracted, chunksize)
                elif ext in {".json", ".jsonl", ".jsonlines"}:
                    yield from read_json_chunks(extracted, chunksize)


def read_excel_chunks(path: Path, chunksize: int = 50_000) -> Generator[pd.DataFrame, None, None]:
    """
    Read the first worksheet of an Excel (.xlsx) file into a DataFrame.
    Requires ``openpyxl`` (installed via the ``all`` extra).
    """
    df = pd.read_excel(path, sheet_name=0, dtype=str, engine="openpyxl")
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
                    df = pd.read_json(io.StringIO("\n".join(buf)), lines=True, dtype=False)
                    yield df.fillna("").astype(str)
                    buf = []
        if buf:
            df = pd.read_json(io.StringIO("\n".join(buf)), lines=True, dtype=False)
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
