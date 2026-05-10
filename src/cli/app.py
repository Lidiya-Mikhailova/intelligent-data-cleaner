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
        help="Intelligent Document Processing SDK — clean, normalize, deduplicate, translate & export",
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
        normalize: bool = typer.Option(True, "--normalize/--no-normalize", help="Apply text normalization"),
        clean: bool = typer.Option(True, "--clean/--no-clean", help="Apply cleaning"),
        deduplicate: bool = typer.Option(True, "--deduplicate/--no-deduplicate", help="Apply exact deduplication"),
        translate: Optional[str] = typer.Option(
            None, "--translate", "-t", help="Translate to language code (e.g., en, ru, es)"
        ),
        export: Optional[str] = typer.Option(
            None, "--export", "-e", help="Export format (csv, json, jsonl, xlsx, txt, pdf)"
        ),
        output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path"),
        preview: bool = typer.Option(False, "--preview", "-p", help="Preview result in console"),
        config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to YAML/JSON config file"),
    ):
        Document.setup_logging()

        if config:
            doc = Document.from_config(_resolve_path(config), override_input=input_file)
        else:
            doc = Document.from_file(_resolve_path(input_file))
            stages = []
            if normalize:
                stages.append("normalize")
            if clean:
                stages.append("clean")
            if deduplicate:
                stages.append("deduplicate")
            if translate:
                stages.append("translate")

            if stages:
                doc = doc.run_pipeline(stages)

        if preview:
            console.print(doc.preview())

        if export:
            result = doc.export(export, output_path=_resolve_path(output) if output else None)
            if isinstance(result, Path):
                console.print(f"[green]Exported to: {result}[/]")
            else:
                console.print(f"[green]Exported {len(result)} bytes[/]")

    @app.command()
    def convert(
        input_file: str = typer.Argument(..., help="Path to input file"),
        to: str = typer.Option("csv", "--to", "-t", help="Output format (csv, json, jsonl, xlsx, txt, pdf)"),
        output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path (optional)"),
    ):
        Document.setup_logging()
        doc = Document.from_file(_resolve_path(input_file))
        result = doc.export(to, output_path=_resolve_path(output) if output else None)
        if isinstance(result, Path):
            console.print(f"[green]Converted to: {result}[/]")
        else:
            console.print(f"[green]Exported {len(result)} bytes[/]")

    @app.command()
    def scan(
        input_file: str = typer.Argument(..., help="Path to scanned PDF or image"),
        engine: str = typer.Option("tesseract", "--engine", "-e", help="OCR engine (tesseract, paddle)"),
        export: Optional[str] = typer.Option(None, "--export", "-f", help="Export format"),
        output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path"),
        preview: bool = typer.Option(False, "--preview", "-p", help="Preview result"),
    ):
        Document.setup_logging()
        doc = Document.from_scan(_resolve_path(input_file), engine=engine)
        doc.clean()

        if preview:
            console.print(doc.preview())

        if export:
            result = doc.export(export, output_path=_resolve_path(output) if output else None)
            if isinstance(result, Path):
                console.print(f"[green]Exported to: {result}[/]")
            else:
                console.print(f"[green]Exported {len(result)} bytes[/]")

    @app.command()
    def run(
        config: str = typer.Argument(..., help="Path to YAML/JSON config file"),
    ):
        Document.setup_logging()
        doc = Document.from_config(_resolve_path(config))
        console.print(doc.preview())

    @app.command()
    def info(
        input_file: str = typer.Argument(..., help="Path to input file"),
    ):
        Document.setup_logging()
        doc = Document.from_file(_resolve_path(input_file))
        console.print(doc.preview(rows=5))

    @app.command()
    def formats():
        """List all supported input/output formats."""
        supported = Document.list_exporters()

        console.print("[bold cyan]Supported Input Formats:[/]")
        console.print("  CSV, TXT, JSON, JSONL, Excel (XLSX), PDF, ZIP")
        console.print("  Scanned PDFs and images (PNG, JPG, TIFF) via OCR")
        console.print()
        console.print("[bold cyan]Supported Export Formats:[/]")
        for fmt in supported:
            console.print(f"  - {fmt}")

    # ── Replay Commands ─────────────────────────────────────────────

    @app.command()
    def replay_silver(
        source_file: str = typer.Argument(..., help="Source file path to replay from silver"),
        export: Optional[str] = typer.Option(None, "--export", "-e", help="Export format(s), comma-separated"),
    ):
        """Re-run pipeline from Silver layer using existing silver data."""
        Document.setup_logging()
        doc = Document.from_file(_resolve_path(source_file))
        paths = doc.replay_from_silver(formats=export.split(",") if export else None)
        for p in paths:
            console.print(f"[green]{p.name}[/]")

    @app.command()
    def replay_invalid(
        source_file: str = typer.Argument(..., help="Source file path to reprocess invalid records"),
        export: Optional[str] = typer.Option(None, "--export", "-e", help="Export format(s), comma-separated"),
    ):
        """Load invalid records, strip validation errors, and re-run validation."""
        Document.setup_logging()
        doc = Document.from_file(_resolve_path(source_file))
        paths = doc.reprocess_invalid(formats=export.split(",") if export else None)
        for p in paths:
            console.print(f"[green]{p.name}[/]")

    @app.command()
    def replay_stage(
        source_file: str = typer.Argument(..., help="Source file path"),
        stage: str = typer.Argument(..., help="Stage name to replay from (e.g. normalize, clean, deduplicate)"),
        export: Optional[str] = typer.Option(None, "--export", "-e", help="Export format(s), comma-separated"),
    ):
        """Re-run pipeline from a specific stage checkpoint."""
        Document.setup_logging()
        doc = Document.from_file(_resolve_path(source_file))
        paths = doc.replay_stage(stage, formats=export.split(",") if export else None)
        for p in paths:
            console.print(f"[green]{p.name}[/]")

    @app.command()
    def rebuild(
        source_file: str = typer.Argument(..., help="Source file path to rebuild from bronze"),
        export: Optional[str] = typer.Option(None, "--export", "-e", help="Export format(s), comma-separated"),
    ):
        """Re-run pipeline from Bronze layer, skipping re-ingest."""
        Document.setup_logging()
        doc = Document.from_file(_resolve_path(source_file))
        paths = doc.rebuild_pipeline(formats=export.split(",") if export else None)
        for p in paths:
            console.print(f"[green]{p.name}[/]")

else:
    app = None

    def main() -> int:
        print("Error: typer is not installed.")
        print("Install it with: pip install 'intelligent-data-cleaner[cli]'")
        return 1


if __name__ == "__main__":
    if app:
        app()
