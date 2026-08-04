from __future__ import annotations

import logging
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import List

import pandas as pd
from fpdf import FPDF

logger = logging.getLogger(__name__)

_PDF_EMOJI_MAP = {
    "\U0001f4a9": "[poo]",
    "\U0001f525": "[fire]",
    "\U0001f308": "[rainbow]",
    "\U0001f30d": "[globe]",
}
_PDF_GREEK_MAP = {
    "\u0376": "\u03dc",
    "\u035a": "\u1fbf",
    "\u037d": "",
    "\u0371": "\u03b7",
}


NUMERIC_COLS = {"ID", "Age"}
MAX_COL_WIDTH = 60


def _display_width(s: str) -> int:
    """Display width of a string (CJK / fullwidth chars count as 2)."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def _pad(s: str, width: int, side: str = "left") -> str:
    current = _display_width(s)
    if current > width:
        result = ""
        w = 0
        for ch in s:
            cw = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
            if w + cw > width - 1:
                break
            w += cw
            result += ch
        return result + "…"
    if current == width:
        return s
    padding = " " * (width - current)
    return padding + s if side == "right" else s + padding


def _col_widths(df: pd.DataFrame) -> list[int]:
    return [
        min(max(df[c].astype(str).map(_display_width).max(), _display_width(c)) + 2, MAX_COL_WIDTH) for c in df.columns
    ]


def _align(v: object, width: int, col_name: str) -> str:
    s = str(v)
    side = "right" if col_name in NUMERIC_COLS else "left"
    return _pad(s, width, side)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    """Save DataFrame to a standard UTF-8 CSV file."""
    df.to_csv(path, index=False, encoding="utf-8")
    logger.info("Saved CSV: %s", path.name)


def save_csv_safe(df: pd.DataFrame, path: Path) -> None:
    """Save a human-readable fixed-width text file with table borders."""
    widths = _col_widths(df)
    sep = " │ "
    top = "┌" + "┬".join("─" * w for w in widths) + "┐"
    head_sep = "├" + "┼".join("─" * w for w in widths) + "┤"
    bottom = "└" + "┴".join("─" * w for w in widths) + "┘"

    with open(path, "w", encoding="utf-8") as f:
        f.write(top + "\n")
        f.write(sep.join(_align(c, w, c) for c, w in zip(df.columns, widths)) + "\n")
        f.write(head_sep + "\n")

        for _, row in df.iterrows():
            line = sep.join(_align(row[c], w, c) for c, w in zip(df.columns, widths))
            f.write(line + "\n")

        f.write(bottom + "\n")

    logger.info("Saved safe CSV: %s", path.name)


def save_excel(df: pd.DataFrame, path: Path) -> None:
    """Save DataFrame to Excel with adjusted column widths."""
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="CleanData")
        ws = writer.sheets["CleanData"]
        for idx, col in enumerate(df.columns):
            width = min(max(df[col].astype(str).map(len).max(), len(col)) + 2, 50)
            ws.set_column(idx, idx, width)


def save_txt(df: pd.DataFrame, path: Path) -> None:
    """Save DataFrame as TXT with fixed-width columns and visible separators."""
    widths = _col_widths(df)
    sep = " │ "

    with open(path, "w", encoding="utf-8") as f:
        header = sep.join(_align(c, w, c) for c, w in zip(df.columns, widths))
        f.write(header + "\n")
        f.write("═" * _display_width(header) + "\n")

        for _, row in df.iterrows():
            line = sep.join(_align(row[c], w, c) for c, w in zip(df.columns, widths))
            f.write(line + "\n")

    logger.info("Saved aligned TXT: %s", path.name)


def save_json(df: pd.DataFrame, path: Path) -> None:
    """
    Save DataFrame as a regular JSON array (records).
    """
    df.to_json(path, orient="records", force_ascii=False, indent=2)
    logger.info("Saved JSON: %s", path)


def save_jsonl(df: pd.DataFrame, path: Path) -> None:
    """
    Save DataFrame as JSON Lines.
    """
    df.to_json(path, orient="records", lines=True, force_ascii=False)
    logger.info("Saved JSONL: %s", path)


def _build_pdf(df: pd.DataFrame, font_path: Path | None = None) -> FPDF:
    """Build and return an FPDF object from a DataFrame."""
    pdf = FPDF(format="A4", unit="mm")
    pdf.add_page()
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)

    def _pdf_safe_text(x: object) -> str:
        s = "" if x is None else str(x)
        s = s.replace("\u2022", "-")
        s = s.replace("\u2013", "-")
        s = s.replace("\u2014", "-")
        s = s.replace("\u2018", "'")
        s = s.replace("\u2019", "'")
        s = s.replace("\u201c", '"')
        s = s.replace("\u201d", '"')
        s = s.replace("\u00a0", " ")
        for old, new in _PDF_EMOJI_MAP.items():
            s = s.replace(old, new)
        for old, new in _PDF_GREEK_MAP.items():
            s = s.replace(old, new)
        s = re.sub(r"[^\u0000-\uFFFF]", "", s)
        return s

    if font_path:
        arial_unicode = font_path.parent.parent / "Arial Unicode.ttf"
        if arial_unicode.exists():
            pdf.add_font("ArialUnicode", "", str(arial_unicode), uni=True)
            pdf.set_font("ArialUnicode", size=6)
            logger.info("PDF font: Arial Unicode MS (%s)", arial_unicode)
        elif font_path.exists():
            pdf.add_font("DejaVu", "", str(font_path), uni=True)
            pdf.set_font("DejaVu", size=6)
            logger.info("PDF font: DejaVu (%s)", font_path)
        else:
            pdf.set_font("Arial", size=6)
            logger.warning("PDF font fallback: Arial. Unicode may fail")
    else:
        pdf.set_font("Arial", size=6)
        logger.warning("PDF font fallback: Arial (not found). Unicode may fail")

    cols = df.columns.tolist()
    page_width = pdf.w - pdf.l_margin - pdf.r_margin
    col_width = page_width / max(len(cols), 1)

    for c in cols:
        pdf.cell(col_width, 4, _pdf_safe_text(c), border=1, align="C")
    pdf.ln(4)

    for row in df.itertuples(index=False):
        for v in row:
            pdf.cell(col_width, 4, _pdf_safe_text(v), border=1)
        pdf.ln(4)

    return pdf


def save_pdf(df: pd.DataFrame, path: Path, font_path: Path | None = None) -> None:
    """Save DataFrame as PDF."""
    pdf = _build_pdf(df, font_path=font_path)
    pdf.output(str(path))


def pdf_to_bytes(df: pd.DataFrame, font_path: Path | None = None) -> bytes:
    """Render DataFrame as PDF and return as bytes."""
    pdf = _build_pdf(df, font_path=font_path)
    raw = pdf.output(dest="S")
    if isinstance(raw, bytearray):
        return bytes(raw)
    if isinstance(raw, bytes):
        return raw
    return raw.encode("latin-1")


def save_zip(files: List[Path], output_path: Path) -> Path:
    """
    Package multiple files into a ZIP archive.
    Returns the path to the created ZIP.
    """
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, arcname=f.name)
    logger.info("Saved ZIP: %s", output_path)
    return output_path
