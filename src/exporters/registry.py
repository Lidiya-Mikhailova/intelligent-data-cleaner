from __future__ import annotations

import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.io.writers import (
    pdf_to_bytes,
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


def _export_metadata(df: pd.DataFrame, **extra: Any) -> Dict[str, Any]:
    return {"rows": len(df), "columns": len(df.columns), **extra}


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

        return ExportResult(format=self.format_name, data=bytes_data, path=path, metadata=_export_metadata(df))


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

        return ExportResult(format=self.format_name, data=bytes_data, path=path, metadata=_export_metadata(df))


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

        return ExportResult(format=self.format_name, data=bytes_data, path=path, metadata=_export_metadata(df))


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

        return ExportResult(format=self.format_name, data=bytes_data, path=path, metadata=_export_metadata(df))


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

        return ExportResult(format=self.format_name, data=bytes_data, path=path, metadata=_export_metadata(df))


@register_exporter
class PDFExporter(Exporter):
    format_name = "pdf"

    def export(self, df: pd.DataFrame, output_path: Optional[Path] = None, **kwargs) -> ExportResult:
        font_path: Optional[Path] = kwargs.get("font_path")

        path = None
        if output_path:
            path = Path(output_path)
            save_pdf(df, path, font_path=font_path)

        bytes_data = pdf_to_bytes(df, font_path=font_path)

        return ExportResult(
            format=self.format_name, data=bytes_data, path=path, metadata=_export_metadata(df, font=bool(font_path))
        )


@register_exporter
class ParquetExporter(Exporter):
    format_name = "parquet"

    def export(self, df: pd.DataFrame, output_path: Optional[Path] = None, **kwargs) -> ExportResult:
        compression: Optional[str] = kwargs.get("compression", "snappy")

        data = io.BytesIO()
        df.to_parquet(data, index=False, compression=compression)
        bytes_data = data.getvalue()

        path = None
        if output_path:
            path = Path(output_path)
            df.to_parquet(path, index=False, compression=compression)

        return ExportResult(
            format=self.format_name, data=bytes_data, path=path, metadata=_export_metadata(df, compression=compression)
        )


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

        return ExportResult(format=self.format_name, data=bytes_data, path=path, metadata=_export_metadata(df))
