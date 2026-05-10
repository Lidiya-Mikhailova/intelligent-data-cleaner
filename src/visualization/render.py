from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.core.metadata import DocumentMetadata

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table as RichTable
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def _get_console() -> Any:
    if RICH_AVAILABLE:
        return Console()
    return None


def render_table(
    data: List[Dict[str, Any]],
    title: str = "Document",
    max_rows: int = 20,
) -> str:
    if not data:
        return "[empty]"

    if not RICH_AVAILABLE:
        lines = [f"=== {title} ==="]
        for i, row in enumerate(data[:max_rows]):
            lines.append(f"  Row {i+1}: {row}")
        if len(data) > max_rows:
            lines.append(f"  ... and {len(data) - max_rows} more rows")
        return "\n".join(lines)

    console = _get_console()
    table = RichTable(title=title, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)

    columns = list(data[0].keys())
    for col in columns:
        col_type = type(data[0].get(col, "")).__name__
        style = "green" if col_type == "int" else "default"
        table.add_column(col, style=style, no_wrap=False, overflow="fold")

    for i, row in enumerate(data[:max_rows]):
        vals = [str(i + 1)]
        for col in columns:
            v = row.get(col, "")
            if v is None or v == "":
                vals.append("[dim]—[/]")
            else:
                s = str(v)
                if len(s) > 100:
                    s = s[:97] + "..."
                vals.append(s)
        table.add_row(*vals)

    if len(data) > max_rows:
        table.add_row("[dim]...[/]", *[f"[dim]... ({len(data) - max_rows} more)[/]"] * len(columns))

    with console.capture() as capture:
        console.print(table)
    return capture.get()


def render_dataframe(df: pd.DataFrame, title: str = "Data", max_rows: int = 10) -> str:
    if df.empty:
        return "[empty dataframe]"

    if not RICH_AVAILABLE:
        return str(df.head(max_rows).to_string())

    console = _get_console()
    table = RichTable(title=title, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)

    for col in df.columns:
        style = "green" if df[col].dtype in ("int64", "float64") else "default"
        table.add_column(str(col), style=style, no_wrap=False, overflow="fold")

    for i, (_, row) in enumerate(df.head(max_rows).iterrows()):
        vals = [str(i + 1)]
        for col in df.columns:
            v = row.get(col)
            if pd.isna(v) or v == "":
                vals.append("[dim]—[/]")
            else:
                s = str(v)
                if len(s) > 100:
                    s = s[:97] + "..."
                vals.append(s)
        table.add_row(*vals)

    if len(df) > max_rows:
        extras = ["[dim]...[/]"] * (len(df.columns) + 1)
        table.add_row(*extras)

    with console.capture() as capture:
        console.print(table)
    return capture.get()


def render_metadata(meta: DocumentMetadata) -> str:
    if not RICH_AVAILABLE:
        lines = ["=== Document Metadata ==="]
        for key, val in meta.to_dict().items():
            if key != "custom":
                lines.append(f"  {key}: {val}")
        if meta.custom:
            lines.append(f"  custom: {meta.custom}")
        return "\n".join(lines)

    console = _get_console()
    info = Text()
    info.append("Source: ", style="bold")
    info.append(f"{meta.source or 'memory'}\n")
    info.append("Format: ", style="bold")
    info.append(f"{meta.source_format or 'unknown'}\n")
    info.append("Rows: ", style="bold")
    info.append(f"{meta.row_count}\n")
    info.append("Columns: ", style="bold")
    info.append(f"{meta.column_count}\n")
    info.append("Stages: ", style="bold")
    info.append(f"{', '.join(meta.processing_stages) or 'none'}\n")

    panel = Panel(info, title="Document Metadata", border_style="cyan")

    with console.capture() as capture:
        console.print(panel)
    return capture.get()


def render_diff(before: pd.DataFrame, after: pd.DataFrame, title: str = "Before / After Diff") -> str:
    if not RICH_AVAILABLE:
        lines = [f"=== {title} ==="]
        lines.append(f"Before: {len(before)} rows, {len(before.columns)} cols")
        lines.append(f"After:  {len(after)} rows, {len(after.columns)} cols")
        lines.append(f"Removed: {len(before) - len(after)} rows")
        return "\n".join(lines)

    console = _get_console()
    before_table = RichTable(title=f"Before ({len(before)} rows)", show_header=True, header_style="bold red")
    for col in before.columns[:5]:
        before_table.add_column(str(col))
    for _, row in before.head(5).iterrows():
        before_table.add_row(*[str(v)[:30] for v in row.values[:5]])

    after_table = RichTable(title=f"After ({len(after)} rows)", show_header=True, header_style="bold green")
    for col in after.columns[:5]:
        after_table.add_column(str(col))
    for _, row in after.head(5).iterrows():
        after_table.add_row(*[str(v)[:30] for v in row.values[:5]])

    with console.capture() as capture:
        console.print(Rule(title))
        console.print(f"Removed: {len(before) - len(after)} rows")
        console.print(Panel(before_table, border_style="red"))
        console.print(Panel(after_table, border_style="green"))
    return capture.get()


def render_processing_summary(meta: DocumentMetadata) -> str:
    if not RICH_AVAILABLE:
        lines = ["=== Processing Summary ==="]
        for step in meta.processing_history:
            lines.append(f"  {step.name}: {step.rows_before} -> {step.rows_after} [{step.status}]")
        return "\n".join(lines)

    console = _get_console()
    table = RichTable(title="Processing Summary", show_header=True, header_style="bold cyan")
    table.add_column("Stage", style="cyan")
    table.add_column("Rows Before", justify="right")
    table.add_column("Rows After", justify="right")
    table.add_column("Status")
    table.add_column("Params")

    for step in meta.processing_history:
        status_style = "green" if step.status == "success" else "red"
        params = ", ".join(f"{k}={v}" for k, v in step.params.items()) if step.params else ""
        table.add_row(
            step.name,
            str(step.rows_before),
            str(step.rows_after),
            f"[{status_style}]{step.status}[/]",
            params,
        )

    with console.capture() as capture:
        console.print(table)
    return capture.get()


def render_pipeline_report(
    meta: DocumentMetadata,
    df: pd.DataFrame,
    output_paths: Optional[List[Path]] = None,
) -> str:
    if not RICH_AVAILABLE:
        lines = ["=== Pipeline Report ==="]
        lines.append(render_processing_summary(meta))
        lines.append(render_dataframe(df))
        if output_paths:
            lines.append("Output files:")
            for p in output_paths:
                lines.append(f"  - {p}")
        return "\n".join(lines)

    console = _get_console()
    with console.capture() as capture:
        console.print(Rule("Pipeline Report", style="cyan"))
        console.print(render_metadata(meta))
        console.print()
        console.print(render_processing_summary(meta))
        console.print()
        console.print(render_dataframe(df, title="Result Data"))
        if output_paths:
            console.print()
            paths_text = Text("\n".join(f"  • {p}" for p in output_paths))
            console.print(Panel(paths_text, title="Output Files", border_style="green"))
    return capture.get()
