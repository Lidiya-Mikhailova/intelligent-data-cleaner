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

- `examples/input/sample.txt`

### Run with the example

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
 •	logs/data_cleaner.log (log files are ignored by Git)
```

    
```text
intelligent-data-cleaner
├── src/
│   ├── cli/            # entry point
│   ├── core/           # orchestration
│   ├── io/             # readers/writers/openers
│   └── processing/     # normalization and deduplication
├── examples/
│   └── input/
│       └── sample.txt  # safe demo input
├── raw_data/           # local input (ignored)
├── output/             # local output (ignored)
├── logs/               # runtime logs (tracked only with .gitkeep; *.log ignored)
├── README.md
├── requirements.txt
└── .gitignore
```

