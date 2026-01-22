from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd

from src.processing.dataframe import clean_df
from src.io.readers import load_csv_chunks, read_pdf_chunks, read_json_chunks
from src.io.writers import (
    save_csv,
    save_csv_safe,
    save_excel,
    save_txt,
    save_pdf,
    save_json,
    save_jsonl,
)


@dataclass
class OutputFormats:
    """
    Output formats toggles.

    If values is None/empty -> generate all.
    """
    csv: bool = True
    safe_csv: bool = True
    excel: bool = True
    txt: bool = True
    pdf: bool = True
    json: bool = True
    jsonl: bool = True

    @staticmethod
    def from_iter(values: Optional[Iterable[str]]) -> "OutputFormats":
        """
        Build OutputFormats from CLI-like values:
        ["csv", "xlsx", "txt", "pdf", "safe_csv", "json", "jsonl"].
        """
        if not values:
            return OutputFormats()

        v = {str(x).strip().lower() for x in values}

        return OutputFormats(
            csv=("csv" in v),
            safe_csv=("safe_csv" in v or "safecsv" in v),
            excel=("xlsx" in v or "excel" in v),
            txt=("txt" in v),
            pdf=("pdf" in v),
            json=("json" in v),
            jsonl=("jsonl" in v),
        )


class IntelligentDataCleaner:
    """
    Main orchestrator for intelligent data cleaning.

    This class:
    - Reads raw inputs (CSV/TXT/PDF/JSON/JSONL)
    - Cleans and deduplicates
    - Saves selected output formats
    - Returns generated paths (runner decides what to open)
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.raw_dir = base_dir / "raw_data"
        self.output_dir = base_dir / "output"

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_file(self, file: Path, formats: Optional[OutputFormats] = None) -> List[Path]:
        """
        Process a single file and return generated output paths.
        """
        formats = formats or OutputFormats()
        suffix = file.suffix.lower()

        # ---- Read input ----
        if suffix in {".csv", ".txt"}:
            chunks = [clean_df(chunk) for chunk in load_csv_chunks(file)]
            df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

        elif suffix == ".pdf":
            chunks = [clean_df(page_df) for page_df in read_pdf_chunks(file)]
            df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

        elif suffix in {".json", ".jsonl", ".jsonlines"}:
            chunks = [clean_df(chunk) for chunk in read_json_chunks(file)]
            df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

        else:
            return []

        # ---- Output base name ----
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"CLEANED_{file.stem}_{timestamp}"
        base_path = self.output_dir / base_name

        generated: List[Path] = []

        # ---- Save selected formats ----
        if formats.csv:
            p = base_path.with_suffix(".csv")
            save_csv(df, p)
            generated.append(p)

        if formats.safe_csv:
            p = base_path.with_name(base_name + "_SAFE.csv")
            save_csv_safe(df, p)
            generated.append(p)

        if formats.excel:
            p = base_path.with_suffix(".xlsx")
            save_excel(df, p)
            generated.append(p)

        if formats.txt:
            p = base_path.with_suffix(".txt")
            save_txt(df, p)
            generated.append(p)

        if formats.pdf:
            p = base_path.with_suffix(".pdf")
            # If you want to pass a font path later, do it here
            save_pdf(df, p, font_path=None)
            generated.append(p)

        if formats.json:
            p = base_path.with_suffix(".json")
            save_json(df, p)
            generated.append(p)

        if formats.jsonl:
            p = base_path.with_suffix(".jsonl")
            save_jsonl(df, p)
            generated.append(p)

        return generated