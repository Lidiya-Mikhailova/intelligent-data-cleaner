from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

from src.core.export_service import export_data
from src.core.utils import cleanup_output
from src.core.validation import classify_records
from src.database import (
    get_db_path,
    get_gold_tables,
    init_db,
    load_stage_result,
    read_table,
    register_bronze,
    write_gold,
    write_silver,
)
from src.database.pipeline_runs import (
    complete_pipeline_run,
    create_pipeline_run,
    update_pipeline_stages,
)
from src.document import Document

logger = logging.getLogger(__name__)


@dataclass
class OutputFormats:
    csv: bool = True
    safe_csv: bool = True
    excel: bool = True
    txt: bool = True
    pdf: bool = True
    json: bool = True
    jsonl: bool = True
    zip: bool = False

    @staticmethod
    def from_iter(values: Optional[Iterable[str]]) -> OutputFormats:
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
            zip=("zip" in v),
        )

    def as_list(self) -> List[str]:
        fmts = []
        if self.csv:
            fmts.append("csv")
        if self.safe_csv:
            fmts.append("safe_csv")
        if self.excel:
            fmts.append("xlsx")
        if self.txt:
            fmts.append("txt")
        if self.pdf:
            fmts.append("pdf")
        if self.json:
            fmts.append("json")
        if self.jsonl:
            fmts.append("jsonl")
        return fmts


class IntelligentDataCleaner:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.raw_dir = base_dir / "bronze"
        self.output_dir = base_dir / "output"
        self.font_dir = base_dir / "fonts" / "dejavu_sans"

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = get_db_path(base_dir)
        self.conn = init_db(self.db_path)

    def process_file(self, file: Path, formats: Optional[OutputFormats] = None) -> List[Path]:
        from src.core.exceptions import UnsupportedFormatError
        from src.normalization.pipeline import Pipeline
        from src.normalization.stages import CleanStage, DeduplicateStage, NormalizeStage

        formats = formats or OutputFormats()
        pipeline_run_id = create_pipeline_run(self.conn, str(file), file.suffix.lstrip("."))

        try:
            doc = Document.from_file(file)
        except UnsupportedFormatError:
            logger.warning("Unsupported file type: %s", file.suffix)
            complete_pipeline_run(self.conn, pipeline_run_id, status="failed", error_message="Unsupported format")
            return []

        raw_df = doc.data.copy()

        pipeline = Pipeline([NormalizeStage(), CleanStage(), DeduplicateStage(fuzzy=False)])
        doc = pipeline.run_with_checkpoints(doc, self.conn, pipeline_run_id, str(file))
        processed_df = doc.data

        if processed_df.empty:
            complete_pipeline_run(self.conn, pipeline_run_id, status="completed", error_message="Empty data")
            return []

        stage_info = []
        row_counts: Dict[str, Dict[str, int]] = {}
        dedup_count = 0
        for step in doc.metadata.processing_history:
            entry = {
                "name": step.name,
                "rows_before": step.rows_before,
                "rows_after": step.rows_after,
                "status": step.status,
            }
            stage_info.append(entry)
            row_counts[step.name] = {"before": step.rows_before, "after": step.rows_after}
            if step.name == "deduplicate":
                dedup_count = step.rows_before - step.rows_after

        update_pipeline_stages(self.conn, pipeline_run_id, stage_info, row_counts)

        register_bronze(self.conn, raw_df, file.name, pipeline_run_id=pipeline_run_id)

        valid_df, invalid_df, quarantine_df = classify_records(processed_df)
        silver_tbl, valid_count, invalid_count, quarantine_count, _ = write_silver(
            self.conn,
            valid_df,
            invalid_df,
            quarantine_df,
            file.name,
            dedup_count=dedup_count,
            pipeline_run_id=pipeline_run_id,
            processing_stages=stage_info,
        )

        if not silver_tbl:
            complete_pipeline_run(self.conn, pipeline_run_id, status="completed", error_message="No valid records")
            return []

        valid_df = read_table(self.conn, silver_tbl)
        gold_tbl = write_gold(
            self.conn,
            valid_df,
            table_name=file.stem,
            source_tables=[silver_tbl],
            pipeline_run_id=pipeline_run_id,
        )

        if not gold_tbl:
            complete_pipeline_run(self.conn, pipeline_run_id, status="completed", error_message="Gold write failed")
            return []

        cleanup_output(self.output_dir)

        fmt_list = formats.as_list()
        if formats.zip:
            fmt_list.append("zip")

        has_any_format = any(
            [
                formats.zip,
                formats.csv,
                formats.safe_csv,
                formats.excel,
                formats.txt,
                formats.pdf,
                formats.json,
                formats.jsonl,
            ]
        )
        gold_data = read_table(self.conn, gold_tbl)
        generated = export_data(
            gold_data,
            self.output_dir,
            formats=fmt_list if has_any_format else [],
            font_dir=self.font_dir,
            base_name=file.stem,
        )

        report_path = self._generate_report(file, valid_count, invalid_count, quarantine_count, dedup_count, gold_tbl)
        if report_path:
            generated.append(report_path)

        complete_pipeline_run(self.conn, pipeline_run_id, status="completed")
        return generated

    def _generate_report(
        self,
        source_file: Path,
        valid_count: int,
        invalid_count: int,
        quarantine_count: int,
        dedup_count: int,
        gold_table: str,
    ) -> Optional[Path]:
        try:
            invalid_tbl = f"silver_invalid_{source_file.stem}"
            invalid_df = self.conn.execute(f"SELECT * FROM {invalid_tbl}").fetchdf()

            report_lines: list[str] = [
                "=" * 60,
                f"  REPORT: {source_file.name}",
                "=" * 60,
                "",
                f"Source file:        {source_file.name}",
                f"Valid records:      {valid_count}",
                f"Invalid records:    {invalid_count}",
                f"Quarantine records: {quarantine_count}",
                f"Duplicates removed: {dedup_count}",
                "",
                "-" * 60,
                "  VALIDATION ERRORS",
                "-" * 60,
            ]

            if invalid_df.empty:
                report_lines.append("  No validation errors.")
            else:
                for _, row in invalid_df.iterrows():
                    error = row.get("validation_error", "Unknown error")
                    lines = error.split("\n")
                    parts = []
                    current_field = None
                    for line in lines:
                        s = line.strip()
                        if not s or "For further information" in s or "https://" in s or "validation error" in s:
                            continue
                        if not line.startswith(" ") and not line.startswith("\t"):
                            current_field = s
                        elif current_field and "[" in s:
                            reason = s.split("[")[0].strip()
                            if reason.startswith("Value error, "):
                                reason = reason[len("Value error, ") :]
                            parts.append(f"{current_field}: {reason}")
                    short = " | ".join(parts) if parts else lines[0].strip()
                    show = {k: v for k, v in row.items() if k in ("ID", "Name") and v}
                    row_data = ", ".join(f"{k}: {v}" for k, v in show.items())
                    report_lines.append(f"  {short}")
                    if row_data:
                        report_lines.append(f"  -> {row_data}")
                    report_lines.append("")

            report_lines.extend(["", "=" * 60])

            report_path = self.output_dir / f"report_{source_file.stem}.txt"
            report_path.write_text("\n".join(report_lines), encoding="utf-8")
            logger.info("Report generated: %s", report_path.name)
            return report_path

        except Exception as e:
            logger.warning("Failed to generate report: %s", e)
            return None

    def process_all(self, formats: Optional[OutputFormats] = None) -> List[Path]:
        formats = formats or OutputFormats()
        all_generated: List[Path] = []

        if not self.raw_dir.exists():
            logger.warning("Bronze directory does not exist: %s", self.raw_dir)
            return all_generated

        for f in sorted(self.raw_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in {".csv", ".txt", ".pdf", ".json", ".jsonl", ".jsonlines", ".zip"}:
                try:
                    generated = self.process_file(f, formats)
                    all_generated.extend(generated)
                except Exception as e:
                    logger.error("Failed to process %s: %s", f.name, e)

        return all_generated

    def _silver_from_processed(self, processed_df, source_file, dedup_count, pipeline_run_id, stage_info):
        valid_df, invalid_df, quarantine_df = classify_records(processed_df)
        return write_silver(
            self.conn,
            valid_df,
            invalid_df,
            quarantine_df,
            source_file,
            dedup_count=dedup_count,
            pipeline_run_id=pipeline_run_id,
            processing_stages=stage_info,
        )

    def _finalize(
        self,
        source_file: str,
        silver_tbl: str,
        pipeline_run_id: int,
        formats: OutputFormats,
        valid_count: int,
        invalid_count: int,
        quarantine_count: int,
        dedup_count: int,
    ) -> List[Path]:
        if not silver_tbl:
            complete_pipeline_run(self.conn, pipeline_run_id, status="completed", error_message="No valid records")
            return []

        valid_df = read_table(self.conn, silver_tbl)
        stem = Path(source_file).stem
        gold_tbl = write_gold(
            self.conn,
            valid_df,
            table_name=f"{stem}_rp{pipeline_run_id}",
            source_tables=[silver_tbl],
            pipeline_run_id=pipeline_run_id,
        )

        if not gold_tbl:
            complete_pipeline_run(self.conn, pipeline_run_id, status="completed", error_message="Gold write failed")
            return []

        cleanup_output(self.output_dir)

        gold_data = read_table(self.conn, gold_tbl)
        generated = export_data(
            gold_data,
            self.output_dir,
            formats=formats.as_list(),
            font_dir=self.font_dir,
            base_name=stem,
        )
        report_path = self._generate_report(
            Path(source_file), valid_count, invalid_count, quarantine_count, dedup_count, gold_tbl
        )
        if report_path:
            generated.append(report_path)
        complete_pipeline_run(self.conn, pipeline_run_id, status="completed")
        return generated

    def replay_from_silver(
        self,
        source_file: str,
        stages: Optional[List[str]] = None,
        formats: Optional[OutputFormats] = None,
    ) -> List[Path]:
        from src.normalization.pipeline import Pipeline

        formats = formats or OutputFormats()
        stem = Path(source_file).stem
        pipeline_run_id = create_pipeline_run(self.conn, source_file, "replay_from_silver")

        try:
            valid_tbl = f"silver_valid_{stem}"
            invalid_tbl = f"silver_invalid_{stem}"
            quarantine_tbl = f"silver_quarantine_{stem}"

            frames = []
            for tbl in (valid_tbl, invalid_tbl, quarantine_tbl):
                try:
                    df = self.conn.execute(f"SELECT * FROM {tbl}").fetchdf()
                    if not df.empty:
                        frames.append(df)
                except Exception:
                    continue

            if not frames:
                complete_pipeline_run(self.conn, pipeline_run_id, status="completed", error_message="No silver data")
                return []

            combined = pd.concat(frames, ignore_index=True)

            drop_cols = [c for c in ("validation_error", "quarantine_reasons", "dummy") if c in combined.columns]
            if drop_cols:
                combined = combined.drop(columns=drop_cols)

            doc = Document(combined)
            stage_names = stages or ["normalize", "clean", "deduplicate"]
            pipeline = Pipeline.from_names(stage_names)
            doc = pipeline.run_with_checkpoints(doc, self.conn, pipeline_run_id, source_file)
            processed_df = doc.data

            if processed_df.empty:
                complete_pipeline_run(
                    self.conn, pipeline_run_id, status="completed", error_message="Empty after pipeline"
                )
                return []

            stage_info = []
            dedup_count = 0
            for step in doc.metadata.processing_history:
                entry = {
                    "name": step.name,
                    "rows_before": step.rows_before,
                    "rows_after": step.rows_after,
                    "status": step.status,
                }
                stage_info.append(entry)
                if step.name == "deduplicate":
                    dedup_count = step.rows_before - step.rows_after

            update_pipeline_stages(self.conn, pipeline_run_id, stage_info)

            silver_tbl, valid_count, invalid_count, quarantine_count, _ = self._silver_from_processed(
                processed_df,
                source_file,
                dedup_count,
                pipeline_run_id,
                stage_info,
            )
            return self._finalize(
                source_file,
                silver_tbl,
                pipeline_run_id,
                formats,
                valid_count,
                invalid_count,
                quarantine_count,
                dedup_count,
            )

        except Exception as e:
            logger.error("replay_from_silver failed: %s", e)
            complete_pipeline_run(self.conn, pipeline_run_id, status="failed", error_message=str(e))
            return []

    def reprocess_invalid(
        self,
        source_file: str,
        formats: Optional[OutputFormats] = None,
    ) -> List[Path]:
        formats = formats or OutputFormats()
        stem = Path(source_file).stem
        pipeline_run_id = create_pipeline_run(self.conn, source_file, "reprocess_invalid")

        try:
            invalid_tbl = f"silver_invalid_{stem}"
            try:
                invalid_df = self.conn.execute(f"SELECT * FROM {invalid_tbl}").fetchdf()
            except Exception:
                complete_pipeline_run(self.conn, pipeline_run_id, status="completed", error_message="No invalid table")
                return []

            if invalid_df.empty:
                complete_pipeline_run(
                    self.conn, pipeline_run_id, status="completed", error_message="No invalid records"
                )
                return []

            if "validation_error" in invalid_df.columns:
                invalid_df = invalid_df.drop(columns=["validation_error"])
            invalid_df = invalid_df.drop(columns=[c for c in ("dummy",) if c in invalid_df.columns], errors="ignore")

            valid_df, _invalid_df, _quarantine_df = classify_records(invalid_df)
            silver_tbl, valid_count, invalid_count, quarantine_count, _ = write_silver(
                self.conn,
                valid_df,
                _invalid_df,
                _quarantine_df,
                source_file,
                dedup_count=0,
                pipeline_run_id=pipeline_run_id,
                processing_stages=[],
            )

            generated: List[Path] = []
            if silver_tbl:
                valid_data = read_table(self.conn, silver_tbl)
                gold_tbl = write_gold(
                    self.conn,
                    valid_data,
                    table_name=f"{stem}_reprocessed",
                    source_tables=[silver_tbl],
                    pipeline_run_id=pipeline_run_id,
                )
                if gold_tbl:
                    cleanup_output(self.output_dir)
                    gold_data = read_table(self.conn, gold_tbl)
                    generated = export_data(
                        gold_data,
                        self.output_dir,
                        formats=formats.as_list(),
                        font_dir=self.font_dir,
                        base_name=f"{stem}_reprocessed",
                    )

            complete_pipeline_run(self.conn, pipeline_run_id, status="completed")
            return generated

        except Exception as e:
            logger.error("reprocess_invalid failed: %s", e)
            complete_pipeline_run(self.conn, pipeline_run_id, status="failed", error_message=str(e))
            return []

    def replay_stage(
        self,
        source_file: str,
        stage_name: str,
        stages: Optional[List[str]] = None,
        formats: Optional[OutputFormats] = None,
    ) -> List[Path]:
        from src.normalization.pipeline import FULL_PIPELINE, Pipeline

        formats = formats or OutputFormats()
        pipeline_run_id = create_pipeline_run(self.conn, source_file, f"replay_stage:{stage_name}")

        try:
            stage_df = load_stage_result(self.conn, stage_name, source_file)
            if stage_df is None:
                complete_pipeline_run(
                    self.conn, pipeline_run_id, status="failed", error_message=f"No checkpoint for stage '{stage_name}'"
                )
                return []

            stage_names = stages or FULL_PIPELINE
            pipeline = Pipeline.from_stage(stage_name, stage_names)

            if not pipeline.stages:
                complete_pipeline_run(self.conn, pipeline_run_id, status="completed", error_message="No stages to run")
                return []

            doc = Document(stage_df)
            doc = pipeline.run_with_checkpoints(doc, self.conn, pipeline_run_id, source_file)
            processed_df = doc.data

            if processed_df.empty:
                complete_pipeline_run(
                    self.conn, pipeline_run_id, status="completed", error_message="Empty after pipeline"
                )
                return []

            stage_info = []
            dedup_count = 0
            for step in doc.metadata.processing_history:
                entry = {
                    "name": step.name,
                    "rows_before": step.rows_before,
                    "rows_after": step.rows_after,
                    "status": step.status,
                }
                stage_info.append(entry)
                if step.name == "deduplicate":
                    dedup_count = step.rows_before - step.rows_after

            update_pipeline_stages(self.conn, pipeline_run_id, stage_info)

            silver_tbl, valid_count, invalid_count, quarantine_count, _ = self._silver_from_processed(
                processed_df,
                source_file,
                dedup_count,
                pipeline_run_id,
                stage_info,
            )
            return self._finalize(
                source_file,
                silver_tbl,
                pipeline_run_id,
                formats,
                valid_count,
                invalid_count,
                quarantine_count,
                dedup_count,
            )

        except Exception as e:
            logger.error("replay_stage failed: %s", e)
            complete_pipeline_run(self.conn, pipeline_run_id, status="failed", error_message=str(e))
            return []

    def rebuild_pipeline(
        self,
        source_file: str,
        stages: Optional[List[str]] = None,
        formats: Optional[OutputFormats] = None,
    ) -> List[Path]:
        from src.normalization.pipeline import Pipeline

        formats = formats or OutputFormats()
        stem = Path(source_file).stem
        pipeline_run_id = create_pipeline_run(self.conn, source_file, "rebuild_pipeline")

        try:
            bronze_tbl = f"bronze_{stem}"
            try:
                bronze_df = self.conn.execute(f"SELECT * FROM {bronze_tbl}").fetchdf()
            except Exception:
                complete_pipeline_run(
                    self.conn, pipeline_run_id, status="failed", error_message=f"No bronze table '{bronze_tbl}'"
                )
                return []

            if bronze_df.empty:
                complete_pipeline_run(self.conn, pipeline_run_id, status="completed", error_message="Empty bronze data")
                return []

            doc = Document(bronze_df)
            stage_names = stages or ["normalize", "clean", "deduplicate"]
            pipeline = Pipeline.from_names(stage_names)
            doc = pipeline.run_with_checkpoints(doc, self.conn, pipeline_run_id, source_file)
            processed_df = doc.data

            if processed_df.empty:
                complete_pipeline_run(
                    self.conn, pipeline_run_id, status="completed", error_message="Empty after pipeline"
                )
                return []

            stage_info = []
            dedup_count = 0
            for step in doc.metadata.processing_history:
                entry = {
                    "name": step.name,
                    "rows_before": step.rows_before,
                    "rows_after": step.rows_after,
                    "status": step.status,
                }
                stage_info.append(entry)
                if step.name == "deduplicate":
                    dedup_count = step.rows_before - step.rows_after

            update_pipeline_stages(self.conn, pipeline_run_id, stage_info)

            silver_tbl, valid_count, invalid_count, quarantine_count, _ = self._silver_from_processed(
                processed_df,
                source_file,
                dedup_count,
                pipeline_run_id,
                stage_info,
            )
            return self._finalize(
                source_file,
                silver_tbl,
                pipeline_run_id,
                formats,
                valid_count,
                invalid_count,
                quarantine_count,
                dedup_count,
            )

        except Exception as e:
            logger.error("rebuild_pipeline failed: %s", e)
            complete_pipeline_run(self.conn, pipeline_run_id, status="failed", error_message=str(e))
            return []

    def list_gold(self):
        return get_gold_tables(self.conn)

    def close(self):
        if hasattr(self, "conn"):
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
