import re
from pathlib import Path
from typing import List
import pandas as pd
from fpdf import FPDF


def save_csv(df: pd.DataFrame, path: Path) -> None:
    """Save DataFrame to CSV with UTF-8 encoding and semicolon separator."""
    df.to_csv(path, index=False, encoding="utf-8", sep=";")


def save_csv_safe(df: pd.DataFrame, path: Path) -> None:
    """Save a human-readable CSV-like text file with fixed-width columns."""
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


def save_pdf(df: pd.DataFrame, path: Path, font_path: Path | None = None) -> None:
    """
    Save DataFrame as PDF.

    Args:
        df (pd.DataFrame): DataFrame to save.
        path (Path): Output PDF path.
        font_path (Path | None): Optional custom font path.
    """
    pdf = FPDF(format="A4", unit="mm")
    pdf.add_page()
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=15)

    if font_path and font_path.exists():
        pdf.add_font("DejaVu", "", str(font_path))
        pdf.set_font("DejaVu", size=6)
    else:
        pdf.set_font("Arial", size=6)

    cols = df.columns.tolist()
    page_width = pdf.w - pdf.l_margin - pdf.r_margin
    col_width = page_width / len(cols)

    for c in cols:
        pdf.cell(col_width, 4, c, border=1, align="C")
    pdf.ln(4)

    for row in df.itertuples(index=False):
        for v in row:
            pdf.cell(col_width, 4, str(v), border=1)
        pdf.ln(4)

    pdf.output(str(path))
