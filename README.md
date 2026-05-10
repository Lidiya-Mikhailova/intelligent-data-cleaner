# Intelligent Data Cleaner

Drop a dirty file (CSV, TXT, JSON, PDF) into the pipeline and get cleaned, deduplicated output in any format. Medallion architecture (Bronze → Silver → Gold) with DuckDB persistence and full replayability.

## Features

- **Input:** CSV, TXT, JSON, JSONL, XLSX, PDF (text + scanned via OCR), ZIP
- **Output:** CSV, safe_csv, XLSX, TXT, PDF, JSON, JSONL, ZIP
- **Pipeline:** Ingest → Extract → Normalize → Clean → Deduplicate → Translate → Enrich → Export
- **Validation:** Pydantic-based: records split into VALID / INVALID / QUARANTINE with error preservation
- **Deduplication:** Exact + fuzzy (rapidfuzz), configurable threshold
- **OCR:** Tesseract-based with auto-detection of scanned PDFs
- **Translation:** Google Translate (deep-translator) with Null fallback
- **Replayability:** All intermediate results preserved — replay from any stage, reprocess invalid records, rebuild from bronze
- **Fluent API:** `Document.from_file(path).normalize().clean().deduplicate().export("csv")`

## Installation

```bash
pip install -e .                     # library + idoc CLI (typer required: pip install -e .[cli])
pip install -e .[all]                # everything including openpyxl
```

## Quick Start

### CLI (`idoc`)

```bash
# Process file through Medallion pipeline (Bronze → Silver → Gold → Export)
idoc process input.csv

# Convert format (no cleaning)
idoc convert input.pdf --to csv

# OCR on scanned PDF
idoc scan scan.pdf --export csv

# Run a config-defined pipeline
idoc run pipeline.yaml

# Show file info
idoc info input.json

# List supported formats
idoc formats

# Replay from Silver layer
idoc replay-silver input.csv

# Reprocess invalid records
idoc replay-invalid input.csv

# Replay from a specific stage
idoc replay-stage input.csv normalize

# Rebuild from Bronze
idoc rebuild input.csv
```

### Library

```python
from src import Document

# Fluent pipeline
doc = Document.from_file("bronze/dirty.csv")
doc = doc.normalize().clean().deduplicate()
doc.export("csv", output_path="output/clean.csv")

# Full Medallion pipeline
doc = Document.from_file("input.csv")
paths = doc.process()
```

## Architecture

```
Document API: from_file → normalize → clean → deduplicate → translate → export
                    │
┌───────────────────▼────────────────────────────────────┐
│              Medallion Pipeline (DuckDB)                │
│  Bronze (raw) ──▶ Silver (valid/invalid/quarantine) ──▶ Gold (final) ──▶ Export
│                        │        │
│                   VALID rows  INVALID rows (with errors)
└────────────────────────────────────────────────────────┘
```

All layers are **append-only** — re-running preserves history.

## Replayability

| Method | What it does |
|--------|-------------|
| `replay_from_silver` | Load silver data, strip validation columns, re-run pipeline |
| `reprocess_invalid` | Load invalid records, strip errors, re-validate |
| `replay_stage` | Load a specific stage checkpoint, run remaining stages |
| `rebuild_pipeline` | Load bronze data, re-run full pipeline |

## Project Structure

```
src/
├── cli/              # Typer CLI (app.py) + argparse CLI (runner.py) + console helpers
├── core/             # Orchestration: cleaner.py (IntelligentDataCleaner), export_service.py, validation.py
├── database/         # DuckDB layers: bronze.py, silver.py, gold.py, export.py, pipeline_runs.py, connection.py
├── document.py       # Document class — the only public API
├── exporters/        # registry.py with 8 exporters (CSV, JSON, JSONL, XLSX, TXT, PDF, safe_csv)
├── io/               # readers.py, writers.py, ocr.py
├── normalization/    # Pipeline framework: pipeline.py, stages.py, text.py, structural.py, deduplication.py
├── translation/      # engine.py
├── validation/       # models.py (SilverRecord)
└── visualization/    # render.py, reports.py
```

## Output Formats

| Flag | Description |
|------|-------------|
| `csv` | UTF-8 CSV |
| `safe_csv` | Fixed-width human-readable CSV |
| `xlsx` | Excel workbook with auto-sized columns |
| `txt` | Fixed-width table |
| `pdf` | A4 PDF with DejaVu Sans / Arial Unicode |
| `json` | Pretty-printed JSON array |
| `jsonl` | JSON Lines (one object per line) |
| `zip` | Archive of all exported files |

## License

MIT
