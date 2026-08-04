from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import pandas as pd

from src.normalization.base import ProcessingStage, is_text_dtype

if TYPE_CHECKING:
    from src.document import Document

logger = logging.getLogger(__name__)


class IngestStage(ProcessingStage):
    name = "ingest"

    def __init__(
        self,
        path: Optional[Union[str, Path]] = None,
        source: Optional[str] = None,
        data: Any = None,
        format: Optional[str] = None,
    ):
        self._path = Path(path) if path else None
        self._source = source
        self._data = data
        self._format = format

    def process(self, doc: Document) -> Document:
        if self._path is not None:
            return self._from_file()
        if self._source == "text" and isinstance(self._data, str):
            return self._from_text()
        if self._source in ("dict", "memory"):
            return self._from_dict()
        if self._source == "bytes":
            return self._from_bytes()
        return doc.transform(lambda df: df, "ingest")

    def _from_file(self) -> Document:
        from src.core.exceptions import UnsupportedFormatError
        from src.core.metadata import DocumentMetadata, ProcessingStep
        from src.document import Document as Doc
        from src.io.readers import (
            load_csv_chunks,
            read_json_chunks,
            read_pdf_chunks,
            read_txt_chunks,
            read_zip_chunks,
        )

        path = self._path
        suffix = path.suffix.lower()
        readers = {
            ".csv": load_csv_chunks,
            ".txt": read_txt_chunks,
            ".json": read_json_chunks,
            ".jsonl": read_json_chunks,
            ".jsonlines": read_json_chunks,
            ".pdf": read_pdf_chunks,
            ".zip": read_zip_chunks,
        }
        reader = readers.get(suffix)
        if reader is None:
            raise UnsupportedFormatError(f"Unsupported file format: {suffix}")

        chunks = list(reader(path))
        data = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

        meta = DocumentMetadata(
            source=str(path),
            source_format=suffix.lstrip("."),
            source_size_bytes=path.stat().st_size,
        )
        meta.add_step(ProcessingStep(name="ingest", rows_before=0, rows_after=len(data)))
        return Doc(data, metadata=meta)

    def _from_text(self) -> Document:
        import io

        import pandas as pd

        from src.core.metadata import DocumentMetadata, ProcessingStep
        from src.document import Document as Doc
        from src.io.readers import _detect_separator, _parse_kv_lines

        text = self._data.strip()
        first_line = text.split("\n", 1)[0] if text else ""
        has_sep = _detect_separator(text)
        is_csv = has_sep and "," in first_line and ":" not in first_line and "=" not in first_line

        if is_csv:
            df = pd.read_csv(io.StringIO(text), dtype=str, on_bad_lines="skip").fillna("")
            meta = DocumentMetadata(source="memory:text", source_format="csv")
        else:
            lines = [ln for ln in text.split("\n") if ln.strip()]
            df = _parse_kv_lines(lines)
            meta = DocumentMetadata(source="memory:text", source_format="txt")

        meta.add_step(ProcessingStep(name="ingest", rows_before=0, rows_after=len(df)))
        return Doc(df, metadata=meta)

    def _from_dict(self) -> Document:
        from src.core.metadata import DocumentMetadata, ProcessingStep
        from src.document import Document as Doc

        data = self._data
        if isinstance(data, dict):
            df = pd.DataFrame([data])
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            raise ValueError(f"Expected dict or list[dict], got {type(data)}")
        df = df.fillna("").astype(str)
        meta = DocumentMetadata(source="memory:dict", source_format="dict")
        meta.add_step(ProcessingStep(name="ingest", rows_before=0, rows_after=len(df)))
        return Doc(df, metadata=meta)

    def _from_bytes(self) -> Document:
        import io

        from src.core.exceptions import UnsupportedFormatError
        from src.core.metadata import DocumentMetadata, ProcessingStep
        from src.document import Document as Doc
        from src.io.readers import _parse_kv_lines

        fmt = (self._format or "csv").lower().lstrip(".")
        meta = DocumentMetadata(source="memory:bytes", source_format=fmt)
        data_bytes = self._data

        if fmt == "csv":
            df = pd.read_csv(io.BytesIO(data_bytes), dtype=str, on_bad_lines="skip").fillna("")
        elif fmt == "json":
            df = pd.read_json(io.BytesIO(data_bytes), dtype=False).fillna("").astype(str)
        elif fmt in ("jsonl", "jsonlines"):
            text = data_bytes.decode("utf-8")
            df = pd.read_json(io.StringIO(text), lines=True, dtype=False).fillna("").astype(str)
        elif fmt == "txt":
            text = data_bytes.decode("utf-8")
            lines = [ln for ln in text.split("\n") if ln.strip()]
            df = _parse_kv_lines(lines)
        else:
            raise UnsupportedFormatError(f"Unsupported bytes format: {fmt}")

        meta.add_step(ProcessingStep(name="ingest", rows_before=0, rows_after=len(df)))
        return Doc(df, metadata=meta)


class FormDetectStage(ProcessingStage):
    name = "form_detect"

    def process(self, doc: Document) -> Document:
        from src.forms import detect_form, extract_form

        if doc.data.empty:
            return doc

        source_lines = []
        if "Field" in doc.data.columns and "Value" in doc.data.columns:
            source_lines = (
                doc.data["SourceLine"].dropna().astype(str).tolist()
                if "SourceLine" in doc.data.columns
                else doc.data["Field"].dropna().astype(str).tolist()
            )
        else:
            col = doc.data.columns[0]
            source_lines = doc.data[col].dropna().astype(str).tolist()

        if not source_lines:
            return doc

        form_type = detect_form(source_lines)
        if form_type is None:
            return doc.transform(lambda df: df, "form_detect")

        logger.info("FormDetectStage: detected %s, running form-specific extraction", form_type)
        parsed = extract_form(source_lines, form_type)
        if not parsed.empty:
            from src.core.metadata import ProcessingStep
            from src.document import Document as Doc

            doc.metadata.add_step(ProcessingStep(name="form_detect", rows_before=len(doc), rows_after=len(parsed)))
            return Doc(parsed, metadata=doc.metadata)

        return doc.transform(lambda df: df, "form_detect")


class ExtractStage(ProcessingStage):
    name = "extract"

    def process(self, doc: Document) -> Document:
        if doc.data.shape[1] == 1 and not doc.data.empty:
            col = doc.data.columns[0]
            sample = str(doc.data[col].iloc[0])
            if ":" in sample and len(sample) < 200:
                from src.io.readers import _parse_kv_lines

                lines = doc.data[col].astype(str).tolist()
                parsed = _parse_kv_lines(lines)
                if not parsed.empty and len(parsed.columns) > 1:
                    from src.core.metadata import ProcessingStep
                    from src.document import Document as Doc

                    logger.info("Extract stage: auto-extracted %d rows from raw text", len(parsed))
                    doc.metadata.add_step(ProcessingStep(name="extract", rows_before=len(doc), rows_after=len(parsed)))
                    return Doc(parsed, metadata=doc.metadata)
        return doc.transform(lambda df: df, "extract")


class NormalizeStage(ProcessingStage):
    name = "normalize"

    def __init__(self, fix_encoding: bool = True, normalize_whitespace: bool = True):
        self.fix_encoding = fix_encoding
        self.normalize_whitespace = normalize_whitespace

    def process(self, doc: Document) -> Document:
        from src.normalization.text import normalize_text
        from src.normalization.transform import PolarsTransformer

        def _normalize(df: pd.DataFrame) -> pd.DataFrame:
            transformer = PolarsTransformer(df)
            df = transformer.transform()
            for col in df.columns:
                if is_text_dtype(df[col].dtype):
                    df[col] = df[col].astype(str).apply(normalize_text)
            return df

        return doc.transform(
            _normalize,
            "normalize",
            {"fix_encoding": self.fix_encoding, "normalize_whitespace": self.normalize_whitespace},
        )


class CleanStage(ProcessingStage):
    name = "clean"

    def __init__(self, structural_only: bool = False):
        self.structural_only = structural_only

    def process(self, doc: Document) -> Document:
        from src.normalization.structural import normalize_dataframe, structural_metrics

        def _clean(df: pd.DataFrame) -> pd.DataFrame:
            result = normalize_dataframe(df)
            metrics = structural_metrics(df)
            doc.metadata.quality_metrics.update(metrics)
            return result

        return doc.transform(
            _clean,
            "clean",
            {"structural_only": self.structural_only},
        )


class DeduplicateStage(ProcessingStage):
    name = "deduplicate"

    def __init__(self, threshold: float = 85.0, fuzzy: bool = False, subset: Optional[List[str]] = None):
        self.threshold = threshold
        self.fuzzy = fuzzy
        self.subset = subset

    def process(self, doc: Document) -> Document:
        removed: pd.DataFrame = pd.DataFrame()

        def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
            nonlocal removed
            cols = self.subset or df.columns.tolist()
            if self.fuzzy:
                from src.normalization.deduplication import fuzzy_deduplicate

                mask = pd.Series(True, index=df.index)
                for col in cols:
                    if col in df.columns and is_text_dtype(df[col].dtype):
                        values = df[col].astype(str).tolist()
                        mapping = fuzzy_deduplicate(values, self.threshold)
                        keep = {orig for orig, canon in mapping if orig == canon}
                        mask &= df[col].astype(str).isin(keep)
                removed = df[~mask].copy().reset_index(drop=True)
                return df[mask].reset_index(drop=True)
            else:
                from src.normalization.deduplication import normalize_key

                keys = df[cols].apply(
                    lambda row: "".join(normalize_key(str(x)) for x in row),
                    axis=1,
                )
                dupe_mask = keys.duplicated(keep="first")
                removed = df[dupe_mask].copy().reset_index(drop=True)
                return df[~dupe_mask].copy().reset_index(drop=True)

        result = doc.transform(_deduplicate, "deduplicate", {"threshold": self.threshold, "fuzzy": self.fuzzy})
        if not removed.empty:
            result._removed["deduplicate"] = removed
        return result


class TranslateStage(ProcessingStage):
    name = "translate"

    def __init__(self, target: str = "en", source: Optional[str] = None, columns: Optional[List[str]] = None):
        self.target = target
        self.source = source
        self.columns = columns

    def process(self, doc: Document) -> Document:
        from src.translation.engine import translate_dataframe

        def _translate(df: pd.DataFrame) -> pd.DataFrame:
            return translate_dataframe(df, target=self.target, source=self.source, columns=self.columns)

        return doc.transform(_translate, "translate", {"target": self.target, "source": self.source or "auto"})


class EnrichStage(ProcessingStage):
    name = "enrich"

    def __init__(self, rules: Optional[Dict[str, Any]] = None):
        self.rules = rules or {}

    def process(self, doc: Document) -> Document:
        def _enrich(df: pd.DataFrame) -> pd.DataFrame:
            for col_name, default_value in self.rules.items():
                if col_name not in df.columns:
                    df[col_name] = str(default_value)
            return df

        return doc.transform(_enrich, "enrich", self.rules)


class ExportStage(ProcessingStage):
    name = "export"

    def __init__(self, fmt: Optional[str] = None, output_path: Optional[str] = None, **kwargs):
        self.fmt = fmt
        self.output_path = output_path
        self.kwargs = kwargs

    def process(self, doc: Document) -> Document:
        if self.fmt:
            doc.export(self.fmt, output_path=self.output_path, **self.kwargs)
        else:
            logger.info("Export stage: no export format configured; skipping")
        return doc
