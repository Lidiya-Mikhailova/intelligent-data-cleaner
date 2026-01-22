# Intelligent Data Cleaner

A modular Python project for cleaning, normalizing, and deduplicating semi-structured data.

The pipeline processes CSV, TXT, JSON, JSONL, and text-based PDF inputs, applies text normalization and strict deduplication, and exports cleaned data to multiple formats.

## Features

- Text normalization (Unicode normalization, control character removal, formatting)
- Strict duplicate removal across rows
- Chunk-based processing for large files
- Inputs: CSV, TXT, JSON, JSONL, PDF (text-based)
- Outputs: CSV, SAFE_CSV, XLSX, TXT, PDF, JSON, JSONL
- Modular architecture for easy extension
- Optional auto-open of generated files (`--open`)

## Notes / Limitations

- Scanned PDFs (image-based) require OCR. The OCR/scanner step is optional and may be added later.

## Example

This repository contains a small, safe example input file:

- `examples/input/sample.txt`

### Run with the example

1.Copy the example file to `raw_data/`:
```bash
cp examples/input/sample.txt raw_data/
```

2.Run the pipeline:
```bash
python -m src.cli.runner
```

3.Check generated files:
```bash
ls -la output/
```

4.Check logs (generated locally):
```logs/data_cleaner.log```

Usage

Install dependencies:
```bash
pip install -r requirements.txt
```
Put your input files into raw_data/, then run:
```bash
python -m src.cli.runner
```

Select output 

Generate only specific output
```bash
python -m src.cli.runner --formats xlsx txt
```
Generate CSV + JSON +JSONL
```bash
python -m src.cli.runner --formats csv json jsonl
```


Project structure
```
intelligent-data-cleaner
├── src/
│   ├── cli/            # entry point
│   ├── core/           # orchestration
│   ├── io/             # readers/writers/openers (+ scanner utils)
│   └── processing/
├── examples/
│   └── input/
│       └── sample.txt
├── raw_data/           # local input (ignored)
├── output/             # local output (ignored)
├── logs/               # runtime logs (tracked only with .gitkeep; *.log ignored)
├── README.md
├── requirements.txt
└── .gitignore

```


