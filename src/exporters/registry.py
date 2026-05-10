from __future__ import annotations

import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.io.writers import (
    save_csv,
    save_excel,
    save_json,
    save_jsonl,
    save_pdf,
    save_txt,
)

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    format: str
    data: Optional[bytes] = None
    path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Exporter(ABC):
    format_name: str = "base"

    @abstractmethod
    def export(
        self,
        df: pd.DataFrame,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> ExportResult: ...

    @property
    def suffix(self) -> str:
        return f".{self.format_name}"


_exporter_registry: Dict[str, type[Exporter]] = {}


def register_exporter(cls: type[Exporter]) -> type[Exporter]:
    _exporter_registry[cls.format_name] = cls
    logger.debug("Registered exporter: %s", cls.format_name)
    return cls


def get_exporter(fmt: str) -> Exporter:
    fmt = fmt.lower().replace(".", "")
    cls = _exporter_registry.get(fmt)
    if cls is None:
        raise ValueError(f"No exporter registered for format: {fmt}")
    return cls()


def list_exporters() -> List[str]:
    return list(_exporter_registry.keys())


@register_exporter
class CSVExporter(Exporter):
    format_name = "csv"

    def export(self, df: pd.DataFrame, output_path: Optional[Path] = None, **kwargs) -> ExportResult:
        data = io.BytesIO()
        df.to_csv(data, index=False, encoding="utf-8")
        bytes_data = data.getvalue()

        path = None
        if output_path:
            path = Path(output_path)
            save_csv(df, path)

        return ExportResult(format="csv", data=bytes_data, path=path)


@register_exporter
class JSONExporter(Exporter):
    format_name = "json"

    def export(self, df: pd.DataFrame, output_path: Optional[Path] = None, **kwargs) -> ExportResult:
        data = io.BytesIO()
        df.to_json(data, orient="records", force_ascii=False, indent=2)
        bytes_data = data.getvalue()

        path = None
        if output_path:
            path = Path(output_path)
            save_json(df, path)

        return ExportResult(format="json", data=bytes_data, path=path)


@register_exporter
class JSONLExporter(Exporter):
    format_name = "jsonl"

    def export(self, df: pd.DataFrame, output_path: Optional[Path] = None, **kwargs) -> ExportResult:
        data = io.BytesIO()
        df.to_json(data, orient="records", lines=True, force_ascii=False)
        bytes_data = data.getvalue()

        path = None
        if output_path:
            path = Path(output_path)
            save_jsonl(df, path)

        return ExportResult(format="jsonl", data=bytes_data, path=path)


@register_exporter
class ExcelExporter(Exporter):
    format_name = "xlsx"

    def export(self, df: pd.DataFrame, output_path: Optional[Path] = None, **kwargs) -> ExportResult:
        data = io.BytesIO()
        with pd.ExcelWriter(data, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Data")
            ws = writer.sheets["Data"]
            for idx, col in enumerate(df.columns):
                width = min(max(df[col].astype(str).map(len).max(), len(col)) + 2, 50)
                ws.set_column(idx, idx, width)
        bytes_data = data.getvalue()

        path = None
        if output_path:
            path = Path(output_path)
            save_excel(df, path)

        return ExportResult(format="xlsx", data=bytes_data, path=path)


@register_exporter
class TXTExporter(Exporter):
    format_name = "txt"

    def export(self, df: pd.DataFrame, output_path: Optional[Path] = None, **kwargs) -> ExportResult:
        data = io.BytesIO()
        text = df.to_string(index=False)
        data.write(text.encode("utf-8"))
        bytes_data = data.getvalue()

        path = None
        if output_path:
            path = Path(output_path)
            save_txt(df, path)

        return ExportResult(format="txt", data=bytes_data, path=path)


@register_exporter
class PDFExporter(Exporter):
    format_name = "pdf"

    def export(self, df: pd.DataFrame, output_path: Optional[Path] = None, **kwargs) -> ExportResult:
        font_path: Optional[Path] = kwargs.get("font_path")

        path = None
        if output_path:
            path = Path(output_path)
            save_pdf(df, path, font_path=font_path)

        bytes_data = b""
        if not output_path:
            from fpdf import FPDF

            pdf = FPDF(format="A4", unit="mm")
            pdf.add_page()
            pdf.set_margins(10, 10, 10)
            pdf.set_auto_page_break(auto=True, margin=15)
            if font_path:
                pdf.add_font("DocFont", "", str(font_path), uni=True)
                pdf.set_font("DocFont", size=6)
            else:
                pdf.set_font("Arial", size=6)
            cols = df.columns.tolist()
            page_width = pdf.w - pdf.l_margin - pdf.r_margin
            col_width = page_width / max(len(cols), 1)
            for c in cols:
                pdf.cell(col_width, 4, str(c), border=1, align="C")
            pdf.ln(4)
            for row in df.itertuples(index=False):
                for v in row:
                    safe = str(v).encode("ascii", errors="replace").decode("ascii")
                    pdf.cell(col_width, 4, safe, border=1)
                pdf.ln(4)
            bytes_data = pdf.output(dest="S").encode("latin-1")

        return ExportResult(format="pdf", data=bytes_data, path=path)


@register_exporter
class SafeCSVExporter(Exporter):
    format_name = "safe_csv"

    def export(self, df: pd.DataFrame, output_path: Optional[Path] = None, **kwargs) -> ExportResult:
        from src.io.writers import save_csv_safe

        data = io.BytesIO()
        text = df.to_string(index=False)
        data.write(text.encode("utf-8"))
        bytes_data = data.getvalue()

        path = None
        if output_path:
            path = Path(output_path)
            save_csv_safe(df, path)

        return ExportResult(format="safe_csv", data=bytes_data, path=path)
