from __future__ import annotations

from pathlib import Path
from typing import List

from src.cli.opener import open_file

SUPPORTED_EXTENSIONS = {".csv", ".txt", ".pdf", ".json", ".jsonl", ".jsonlines", ".zip"}


def list_raw_files(base_dir: Path) -> list[Path]:
    raw_dir = base_dir / "bronze"
    if not raw_dir.exists():
        return []
    files = []
    for f in sorted(raw_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(f)
    return files


def print_file_menu(files: list[Path]) -> None:
    print("\n" + "=" * 60)
    print("  Intelligent Data Cleaner")
    print("=" * 60)
    print("\nAvailable files in bronze/:\n")
    for i, f in enumerate(files, 1):
        size_kb = f.stat().st_size / 1024
        print(f"  [{i}] {f.name}  ({size_kb:.1f} KB)")
    print("\n  [0] Exit\n")
    print("-" * 60)


def ask_file_choice(files: list[Path]) -> Path | None:
    while True:
        choice = input("Select file number: ").strip()
        if choice == "0":
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                return files[idx]
        except ValueError:
            pass
        if choice:
            p = Path(choice).expanduser()
            if p.exists():
                return p.resolve()
            print(f"  File not found: {choice}")
        print("  Enter a valid number or file path.")


def ask_formats() -> List[str]:
    print("\nExport formats:")
    print("  1. CSV          2. XLSX (Excel)")
    print("  3. TXT          4. PDF")
    print("  5. JSON         6. JSONL")
    print("  7. ALL")
    print()
    choice = input("Select (number, name, or comma-separated, or 'all'): ").strip().lower()
    if not choice or choice == "7" or "all" in choice:
        return []
    selected = set(s.strip() for s in choice.split(","))
    name_map = {
        "csv": "csv",
        "1": "csv",
        "xlsx": "xlsx",
        "excel": "xlsx",
        "2": "xlsx",
        "txt": "txt",
        "text": "txt",
        "3": "txt",
        "pdf": "pdf",
        "4": "pdf",
        "json": "json",
        "5": "json",
        "jsonl": "jsonl",
        "6": "jsonl",
    }
    fmt_set = set()
    for s in selected:
        mapped = name_map.get(s)
        if mapped:
            fmt_set.add(mapped)
    return list(fmt_set)


def open_generated(generated: list[Path]) -> None:
    for p in generated:
        try:
            open_file(p)
            print(f"  Opened: {p.name}")
        except Exception as e:
            print(f"  Could not open {p.name}: {e}")


def print_gold_menu(gold_df) -> None:
    print("\n" + "=" * 60)
    print("  Available gold tables")
    print("=" * 60)
    print()
    if gold_df.empty:
        print("  No gold tables yet. Process a file first.")
    else:
        print(gold_df.to_string(index=False))
    print()


def ask_mode() -> str:
    print("\n" + "=" * 60)
    print("  What do you want to do?")
    print("=" * 60)
    print()
    print("  1. Simple conversion - just convert file format")
    print("  2. Data processing - clean, deduplicate, validate data")
    print()
    while True:
        choice = input("Select (1 or 2): ").strip()
        if choice == "1":
            return "convert"
        if choice == "2":
            return "process"
        print("  Enter 1 or 2.")
