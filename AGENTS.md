# Intelligent Data Cleaner

Clean CSV/TXT/JSON/PDF — fast.

```bash
pip install -e ".[dev,all]"
python -m pytest tests/ -q
```

## Core flow

```
from_file → normalize → clean → deduplicate → remove_rows (optional) → export
```

## Quick commands

```bash
idoc process input.csv
idoc convert input.pdf --to csv
idoc review
idoc quarantine list
```

## Test suite

```bash
pytest tests/ -q
pytest tests/test_normalization.py -v
pytest tests/test_deduplication.py -v
pytest tests/test_validation.py -v
pytest tests/test_dq.py -v
```

## Key files

- `document.py` — единственный public класс
- `normalization/stages.py` — все этапы
- `exporters/registry.py` — `@register_exporter`
- `src/review/` — `ReportSummary`, `DataQualityMetrics`, `QuarantineRecord`, `build_report_summary`, `format_report_txt`
- `src/dq/` — `DQ_COLUMNS`, `DQService`, `DQStage`, `strip_dq_columns`, all check functions
