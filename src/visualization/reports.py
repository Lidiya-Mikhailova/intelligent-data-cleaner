from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from src.core.metadata import DocumentMetadata


def generate_report(
    meta: DocumentMetadata,
    df: pd.DataFrame,
    output_path: Optional[Path] = None,
    validation_errors: Optional[pd.DataFrame] = None,
) -> str:
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  Document Processing Report")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Source:       {meta.source or 'memory'}")
    lines.append(f"Format:       {meta.source_format or 'unknown'}")
    lines.append(f"Total rows:   {meta.row_count}")
    lines.append(f"Total cols:   {meta.column_count}")
    lines.append("")
    lines.append("-" * 60)
    lines.append("  Processing Stages")
    lines.append("-" * 60)
    for step in meta.processing_history:
        status = "\u2713" if step.status == "success" else "\u2717"
        params = f" ({step.params})" if step.params else ""
        lines.append(f"  {status} {step.name}: {step.rows_before} \u2192 {step.rows_after} rows{params}")

    lines.append("")
    lines.append("-" * 60)
    lines.append("  Columns")
    lines.append("-" * 60)
    for col in df.columns:
        non_null = df[col].astype(str).apply(lambda x: x.strip() != "").sum()
        lines.append(f"  \u2022 {col}: {non_null}/{len(df)} non-empty")

    if validation_errors is not None and not validation_errors.empty:
        lines.append("")
        lines.append("-" * 60)
        lines.append("  Validation Errors")
        lines.append("-" * 60)
        for _, row in validation_errors.iterrows():
            error = row.get("validation_error", "Unknown error")
            lines.append(f"  \u2717 {error[:200]}")

    lines.append("")
    lines.append("=" * 60)

    report = "\n".join(lines)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")

    return report
