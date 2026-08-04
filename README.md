# Intelligent Data Cleaner

**загрузил → почистил → поправил → выбрал формат → выгрузил**

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
doc = doc.deduplicate()         # fuzzy dedup (default, rapidfuzz)
doc = doc.deduplicate(fuzzy=True, threshold=85.0, subset=["Name", "Age"])
doc = doc.translate(target="en")
doc = doc.validate()            # DQ checks
```

### 3. Inspect & Fix

```python
# Посмотреть дубликаты (не удаляет!)
dupes = doc.find_duplicates(fuzzy=False, subset=["Name", "Age"])
print(dupes)

# Удалить конкретные строки
doc = doc.remove_rows([3, 7])
doc = doc.keep_rows(lambda r: r["Name"] != "")

# Посмотреть что удалил deduplicate
print(doc.duplicates)
print(doc.removed)  # строки, удалённые на этапе deduplicate

# Классификация (VALID / INVALID / QUARANTINE)
valid, invalid, quarantine = doc.classify()
r = doc.review
print(f"valid={r.rows_valid}, invalid={r.rows_invalid}, quarantine={r.rows_quarantine}")

# Подозрительные строки (DQ warnings)
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

> Примечание: `doc.export("csv", output_path=...)` сохраняет CSV в выровненном
> табличном виде (удобно для чтения человеком, но не стандартный CSV). Для
> стандартного CSV используйте возврат байтов `data = doc.export("csv")`.

### Preview

```python
print(doc.preview(rows=10))
print(doc.report())
```

## CLI

```bash
idoc process input.csv                  # clean + dedup + export
idoc process input.csv --no-deduplicate
idoc process input.csv --translate en -e csv
idoc convert input.pdf --to csv         # без очистки
idoc info input.csv
idoc formats
```

## Полный пример

```python
from src.document import Document

doc = Document.from_file("bronze/dirty.csv")
doc = doc.normalize().clean()

# смотрим дубликаты
print(doc.find_duplicates(fuzzy=False))

# удаляем мусорную строку 7
doc = doc.remove_rows(7)

# дедуплицируем остальное
doc = doc.deduplicate()

# смотрим что удалилось
print(doc.duplicates)

# экспорт
doc.export("csv", output_path="output/clean.csv")
```

## Directory Layout

```
src/
├── document.py          # Document — единственный public класс
├── core/                # metadata, validation, exceptions
├── normalization/       # pipeline, stages, text, deduplication
├── exporters/           # registry + 8 exporters
├── dq/                  # quality checks
├── review/              # модели отчётов и карантина
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
