# Intelligent Data Cleaner

A modular Python project for cleaning, normalizing, and deduplicating semi-structured data.

The pipeline processes **CSV, TXT, JSON, and text-based PDF** inputs, applies text normalization, removes strict duplicates, and exports cleaned results to multiple formats.

## Features

- Text normalization (Unicode normalization, control character removal, formatting)
- Strict duplicate removal across rows
- Chunk-based processing for large files
- Inputs: CSV, TXT, JSON, **PDF (text-based)**
- Outputs: CSV, XLSX, TXT, PDF
- Modular architecture for easy extension (including API integrations)

> Note: **Scanned PDFs require OCR** (not included in the current version).



## Example

This repository contains a small, safe example input file:
`examples/input/sample.txt`

# Intelligent Data Cleaner

A modular Python project for cleaning, normalizing, and deduplicating semi-structured data.

<<<<<<< HEAD
1.	Copy the example file to ```raw_data/:```
   ```bash
cp examples/input/sample.txt raw_data/
```

2.	Run the data cleaning pipeline:
  ```bash
python -m src.cli.runner
```
   
3.	Check generated files in the output directory:
   ```bash
ls -la output/
```

4.	Check logs (generated locally):
   ```bash
   logs/data_cleaner.log (log files are ignored by Git)
```

    
```text

The pipeline processes **CSV, TXT, PDF, JSON/JSONL** inputs, applies text normalization, removes strict duplicates, and exports cleaned results to multiple formats.

It also supports **scanned PDFs (image-based)** via an optional **scanner/OCR** step.

## Features

- Text normalization (Unicode normalization, control character removal, formatting)
- Strict duplicate removal across rows
- Chunk-based processing for large files
- Inputs: **CSV, TXT, PDF, JSON, JSONL**
- Scanned PDFs: **OCR extraction** (optional)
- Outputs: **CSV, SAFE_CSV, XLSX, TXT, PDF, JSON, JSONL**
- Modular architecture for easy extension
- Optional auto-open of generated files (`--open`)

---

## How it works

1. **Load** input file (chunked for CSV/TXT/JSONL where possible)
2. **Extract text**:
   - PDF with text layer → extract directly
   - **Scanned PDF** → OCR (scanner) to recover text
3. **Normalize + clean** text fields
4. **Deduplicate** with a strict row-level key
5. **Export** to requested formats

---

## Quick start

Install dependencies:
```bash
pip install -r requirements.txt
```

Put your input files into raw_data/, then run:
```bash
python -m src.cli.runner
```

Cleaned results will be written to:
	```•output/```

Logs:
	```•logs/data_cleaner.log```

Select output formats

Generate only specific outputs:
```bash
python -m src.cli.runner --formats xlsx txt
```
Generate CSV + JSON + JSONL:
```bash
python -m src.cli.runner --formats csv json jsonl
```

Open generated files automatically

Open only the generated formats you requested:
```bash
python -m src.cli.runner --formats xlsx txt --open
```

Scanned PDF support (OCR / scanner)

Some PDFs contain no selectable text (they are essentially images). For those files, the project can run an OCR-based scanner.

When OCR runs

     If the PDF page has no extractable text, the scanner will OCR the page
	 If the PDF has a text layer, OCR is skipped (faster and cleaner)
     

Requirements

	 An OCR backend must be installed and accessible locally (example: Tesseract)
	 For best results, use 300 DPI and clear scans

Optional CLI (suggested)

If your scanner supports a flag, you can run:
```bash
python -m src.cli.runner --ocr
```
Or auto mode:
```bash
python -m src.cli.runner --ocr auto
```
(Exact flags depend on your implementation — keep these stable once scanner support is added.)

Recommended outputs

For most client tasks, the best default set is:
	XLSX → easiest for review
	CSV → universal import format
	JSONL → best for pipelines / LLM ingestion

Typical run:
```bash
python -m src.cli.runner --formats xlsx csv jsonl --open
```

Project structure

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


