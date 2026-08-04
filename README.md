# Intelligent Data Cleaner

**load → clean → fix → pick a format → export**

![CI](https://img.shields.io/github/actions/workflow/status/Lidiya-Mikhailova/intelligent-data-cleaner/ci.yml?branch=main&label=CI)
![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12%20|%203.13%20|%203.14-blue)
![License](https://img.shields.io/badge/license-MIT-green)

```bash
pip install -e ".[dev,all]"
```

## Library API

```python
from src.document import Document
```

### 1. Load

```python
doc = Document.from_file("bronze/dirty.csv")
doc = Document.from_file("data.txt")
doc = Document.from_file("data.json")
doc = Document.from_dict([{"Name": "John", "Age": 30}])
doc = Document.from_text("Name: John\nAge: 30")
```

### 2. Clean

```python
doc = doc.normalize()           # encoding, whitespace, unicode
doc = doc.clean()               # structural cleanup
doc = doc.deduplicate()         # exact dedup (default)
doc = doc.deduplicate(fuzzy=True, threshold=85.0, subset=["Name", "Age"])
doc = doc.translate(target="en")
doc = doc.validate()            # DQ checks
```

### 3. Inspect & Fix

```python
# Inspect duplicates (does not remove!)
dupes = doc.find_duplicates(fuzzy=False, subset=["Name", "Age"])
print(dupes)

# Remove specific rows
doc = doc.remove_rows([3, 7])
doc = doc.keep_rows(lambda r: r["Name"] != "")

# See what deduplicate removed
print(doc.duplicates)
print(doc.removed)  # rows removed during deduplication

# Classification (VALID / INVALID / QUARANTINE)
valid, invalid, quarantine = doc.classify()
r = doc.review
print(f"valid={r.rows_valid}, invalid={r.rows_invalid}, quarantine={r.rows_quarantine}")

# Suspicious rows (DQ warnings)
print(doc.suspicious())
print(doc.quarantine)
```

### 4. Export

```python
doc.export("csv", output_path="clean.csv")        # → Path
doc.export("json", output_path="clean.json")
doc.export("xlsx", output_path="clean.xlsx")
doc.export("txt", output_path="clean.txt")
doc.export("pdf", output_path="clean.pdf")
doc.export("jsonl", output_path="clean.jsonl")
doc.export("parquet", output_path="clean.parquet", compression="snappy")
data = doc.export("csv")                           # → bytes
```

### Preview

```python
print(doc.preview(rows=10))
print(doc.report())
```

## CLI

```bash
idoc process input.csv                  # clean + dedup + dq + export
idoc process input.csv --no-deduplicate
idoc process input.csv --no-dq          # skip DQ checks
idoc process input.pdf --forms          # extract W-2/W-4/1099 forms
idoc process input.csv --translate en -e csv
idoc convert input.pdf --to csv         # no cleaning
idoc review                             # latest quality report
idoc quarantine list                    # problematic rows
idoc quarantine export -s q.csv         # export quarantine
idoc info input.csv
idoc formats
```

## Full example

```python
from src.document import Document

doc = Document.from_file("bronze/dirty.csv")
doc = doc.normalize().clean()

# inspect duplicates
print(doc.find_duplicates(fuzzy=False))

# drop junk row 7
doc = doc.remove_rows(7)

# deduplicate the rest
doc = doc.deduplicate()

# see what was removed
print(doc.duplicates)

# export
doc.export("csv", output_path="output/clean.csv")
```

## Directory Layout

```
src/
├── document.py          # the only public class
├── core/                # metadata, validation, exceptions
├── normalization/       # pipeline, stages, text, deduplication
├── exporters/           # registry + 8 exporters
├── dq/                  # quality checks
├── review/              # report & quarantine models
├── io/                  # readers, writers
├── validation/          # Pydantic SilverRecord
├── translation/         # deep-translator engine
├── forms/               # W-2, W-4, 1099
├── visualization/       # preview rendering
└── cli/                 # Typer app
```

## Tests

```bash
python -m pytest tests/ -v        # All
python -m pytest tests/ -q        # Quick
python -m pytest tests/test_normalization.py -v
python -m pytest tests/test_deduplication.py -v
python -m pytest tests/test_validation.py -v
python -m pytest tests/test_dataframe.py -v
python -m pytest tests/test_dq.py -v
```

## License

MIT
