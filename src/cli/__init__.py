from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.document import Document

logger = logging.getLogger(__name__)

try:
    import typer
    from rich.console import Console

    TYPER_AVAILABLE = True
except ImportError:
    TYPER_AVAILABLE = False

if TYPER_AVAILABLE:
    app = typer.Typer(
        name="idoc",
        help="Intelligent Document Processing — clean, deduplicate, translate & export",
        no_args_is_help=True,
    )
    console = Console()
else:
    app = None
    console = None


def _resolve_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


if TYPER_AVAILABLE:

    @app.command()
    def process(
        input_file: str = typer.Argument(..., help="Path to input file"),
        normalize: bool = typer.Option(True, "--normalize/--no-normalize"),
        clean: bool = typer.Option(True, "--clean/--no-clean"),
        deduplicate: bool = typer.Option(True, "--deduplicate/--no-deduplicate"),
        translate: Optional[str] = typer.Option(None, "--translate", "-t", help="Target language (e.g. en, ru)"),
        export: Optional[str] = typer.Option(None, "--export", "-e", help="Output format (csv, json, xlsx, txt, pdf)"),
        output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path"),
        preview: bool = typer.Option(False, "--preview", "-p", help="Preview result"),
    ):
        """Load, clean, optionally translate, and export a file."""
        Document.setup_logging()
        doc = Document.from_file(_resolve_path(input_file))

        stages = []
        if normalize:
            stages.append("normalize")
        if clean:
            stages.append("clean")
        if deduplicate:
            stages.append("deduplicate")

        if stages:
            doc = doc.run_pipeline(stages)

        if translate:
            doc = doc.translate(target=translate)

        if export:
            result = doc.export(export, output_path=_resolve_path(output) if output else None)
            if isinstance(result, Path):
                console.print(f"[green]Exported to: {result}[/]")
            else:
                console.print(f"[green]Exported {len(result)} bytes[/]")

        if preview or not export:
            console.print(doc.preview())

    @app.command()
    def convert(
        input_file: str = typer.Argument(..., help="Path to input file"),
        to: str = typer.Option("csv", "--to", "-t", help="Output format (csv, json, xlsx, txt, pdf)"),
        output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path"),
    ):
        """Convert file format without cleaning."""
        Document.setup_logging()
        doc = Document.from_file(_resolve_path(input_file))
        result = doc.export(to, output_path=_resolve_path(output) if output else None)
        if isinstance(result, Path):
            console.print(f"[green]Converted to: {result}[/]")
        else:
            console.print(f"[green]Exported {len(result)} bytes[/]")

    @app.command()
    def info(input_file: str = typer.Argument(..., help="Path to input file")):
        """Show file preview."""
        Document.setup_logging()
        doc = Document.from_file(_resolve_path(input_file))
        console.print(doc.preview(rows=5))

    @app.command()
    def formats():
        """List supported formats."""
        supported = Document.list_exporters()
        console.print("[bold cyan]Supported Input Formats:[/]")
        console.print("  CSV, TXT, JSON, JSONL, Excel (XLSX), PDF, ZIP")
        console.print()
        console.print("[bold cyan]Supported Export Formats:[/]")
        for fmt in supported:
            console.print(f"  - {fmt}")

    @app.command(name="review")
    def review_cmd(
        report: str = typer.Argument("latest", help="latest or path to review.json"),
    ):
        """Show review report."""
        Document.setup_logging()
        import json

        from src.review import ReportSummary, format_report_txt

        if report != "latest":
            rpath = _resolve_path(report)
            if rpath.suffix == ".json":
                data = json.loads(rpath.read_text(encoding="utf-8"))
                console.print(format_report_txt(ReportSummary(**data)))
                return
            console.print(f"[red]Report not found: {report}[/]")
            raise typer.Exit(1)

        output_dir = Path("output")
        reviews = sorted(output_dir.glob("review_*.json"))
        if not reviews:
            console.print("[yellow]No review reports found.[/]")
            return
        data = json.loads(reviews[-1].read_text(encoding="utf-8"))
        console.print(format_report_txt(ReportSummary(**data)))

    @app.command()
    def quarantine(
        action: str = typer.Argument(..., help="list or export"),
        source: Optional[str] = typer.Option(None, "--source", "-s", help="Output path for export"),
    ):
        """List or export quarantine records."""
        Document.setup_logging()
        output_dir = Path("output")

        if action == "list":
            reviews = sorted(output_dir.glob("review_*.json"))
            if not reviews:
                console.print("[yellow]No review reports found.[/]")
                return
            import json

            data = json.loads(reviews[-1].read_text(encoding="utf-8"))
            q_count = len(data.get("quarantine_records", [])) or data.get("rows_quarantine", 0)
            if not q_count:
                console.print("[green]No quarantine records in latest run.[/]")
                return
            console.print(f"[bold]Quarantine records: {q_count}[/]")
            quarantines = sorted(output_dir.glob("quarantine_*.csv"))
            if quarantines:
                import csv

                with open(quarantines[-1], newline="", encoding="utf-8") as f:
                    for i, row in enumerate(csv.DictReader(f)):
                        reason = row.get("_reason", "")[:70]
                        cat = row.get("_category", "")
                        conf = row.get("_confidence", "")
                        preview = ", ".join(
                            v
                            for k, v in row.items()
                            if not k.startswith("_") and v and str(v) not in ("", "nan", "NaT", "None")
                        )
                        console.print(f"  #{i}  [{cat}] {preview[:60]}")
                        console.print(f"      {reason}")
                        console.print(f"      confidence={conf}")
                        console.print()
        elif action == "export":
            quarantines = sorted(output_dir.glob("quarantine_*.csv"))
            if not quarantines:
                console.print("[yellow]No quarantine CSVs found.[/]")
                return
            latest_q = quarantines[-1]
            out = _resolve_path(source) if source else latest_q
            import shutil

            shutil.copy(latest_q, out)
            console.print(f"[green]Quarantine exported to: {out}[/]")
        else:
            console.print(f"[red]Unknown action: {action}. Use 'list' or 'export'.[/]")
            raise typer.Exit(1)

else:
    app = None

    def main() -> int:
        print("Error: typer is not installed.")
        print("Install it with: pip install 'intelligent-data-cleaner[cli]'")
        return 1


if __name__ == "__main__":
    if app:
        app()
