from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List

import pandas as pd
from fpdf import FPDF

logger = logging.getLogger(__name__)


def save_csv(df: pd.DataFrame, path: Path) -> None:
    """Save DataFrame to CSV with UTF-8 encoding and semicolon separator."""
    df.to_csv(path, index=False, encoding="utf-8", sep=";")


def save_csv_safe(df: pd.DataFrame, path: Path) -> None:
    """Save a human-readable fixed-width text file (CSV-like)."""
    columns: List[str] = df.columns.tolist()
    widths = [max(df[c].astype(str).map(len).max(), len(c)) + 4 for c in columns]

    with open(path, "w", encoding="utf-8") as f:
        header = "".join(c.ljust(w) for c, w in zip(columns, widths))
        f.write(header + "\n")
        f.write("=" * len(header) + "\n")
        for row in df.itertuples(index=False):
            line = "".join(str(v).ljust(w) for v, w in zip(row, widths))
            f.write(line + "\n")


def save_excel(df: pd.DataFrame, path: Path) -> None:
    """Save DataFrame to Excel with adjusted column widths."""
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="CleanData")
        ws = writer.sheets["CleanData"]
        for idx, col in enumerate(df.columns):
            width = min(max(df[col].astype(str).map(len).max(), len(col)) + 2, 50)
            ws.set_column(idx, idx, width)


def save_txt(df: pd.DataFrame, path: Path) -> None:
    """Save DataFrame as TXT with fixed-width columns and sanitized text."""
    columns = df.columns.tolist()
    widths = [max(df[c].astype(str).map(len).max(), len(c)) + 4 for c in columns]

    with open(path, "w", encoding="utf-8") as f:
        header = "".join(c.ljust(w) for c, w in zip(columns, widths))
        f.write(header + "\n")
        f.write("=" * len(header) + "\n")
        for row in df.itertuples(index=False):
            line = "".join(
                re.sub(r"[^\w\s\.\-@А-Яа-яЁё]", "", str(v)).ljust(w)
                for v, w in zip(row, widths)
            )
            f.write(line + "\n")


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


def save_pdf(df: pd.DataFrame, path: Path, font_path: Path | None = None) -> None:
    """Save DataFrame as PDF."""
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
        s = s.replace("\u00A0", " ")
        return s

    if font_path and font_path.exists():
        pdf.add_font("DejaVu", "", str(font_path), uni=True)
        pdf.set_font("DejaVu", size=6)
        logger.info("PDF font: DejaVu (%s)", font_path)
    else:
        pdf.set_font("Arial", size=6)
        logger.warning("PDF font fallback: Arial (font not found). Unicode may fail")

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

    pdf.output(str(path))