# Intelligent Data Cleaner

A modular Python project for cleaning, normalizing, and deduplicating semi-structured data.

The pipeline processes CSV, TXT, and PDF inputs, applies text normalization, removes strict duplicates, and exports cleaned results to multiple formats.

## Features

- Text normalization (Unicode normalization, control character removal, formatting)
- Strict duplicate removal across rows
- Chunk-based processing for large files
- Inputs: CSV, TXT, PDF
- Outputs: CSV, XLSX, TXT, PDF
- Modular architecture for easy extension

## Project Structure

```text
intelligent-data-cleaner
├── src/
│   ├── cli/            # entry point
│   ├── core/           # orchestration
│   ├── io/             # readers/writers/openers
│   └── processing/     # normalization and deduplication
│
├── raw_data/           # local input (ignored)
├── output/             # local output (ignored)
│
├── README.md
├── requirements.txt
└── .gitignore
