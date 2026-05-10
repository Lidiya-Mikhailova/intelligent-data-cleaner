from __future__ import annotations

import argparse
from pathlib import Path

from src.cli.console import (
    ask_file_choice,
    ask_formats,
    ask_mode,
    list_raw_files,
    open_generated,
    print_file_menu,
    print_gold_menu,
)
from src.document import Document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intelligent-data-cleaner",
        description="Clean, normalize and deduplicate raw data files with Medallion architecture (DuckDB).",
    )

    sub = parser.add_subparsers(dest="command")

    process_p = sub.add_parser("process", help="Process a file through bronze -> silver -> gold")
    process_p.add_argument("input_file", type=str, help="Path to input file")
    process_p.add_argument("--formats", nargs="*", default=None, help="Export formats (default: all)")

    list_p = sub.add_parser("list", help="List datasets in the database")
    list_p.add_argument("layer", choices=["bronze", "silver", "gold"], nargs="?", default="gold")

    export_p = sub.add_parser("export", help="Export a gold table to files")
    export_p.add_argument("table", type=str, help="Gold table name")
    export_p.add_argument("--formats", nargs="*", default=None, help="Export formats")

    clean_p = sub.add_parser("clean", help="Clean all files in bronze/")
    clean_p.add_argument("--formats", nargs="*", default=None, help="Export formats (default: all)")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    base_dir = Path(".").resolve()
    Document.setup_logging(base_dir)

    command = getattr(args, "command", None)

    if command == "list":
        df = Document.list_tables(layer=args.layer, base_dir=str(base_dir))
        if df.empty:
            print(f"No {args.layer} tables found.")
            return 0
        if args.layer == "gold":
            print_gold_menu(df)
        else:
            print(df.to_string(index=False))
        return 0

    if command == "export":
        paths = Document.export_table(args.table, base_dir=str(base_dir), formats=args.formats)
        if not paths:
            print("Nothing exported.")
            return 1
        print(f"\nExported {len(paths)} file(s):\n")
        for p in paths:
            print(f"  {p.name}")
        open_generated(paths)
        return 0

    if command == "clean":
        paths = Document.process_all(base_dir=str(base_dir), formats=args.formats)
        if not paths:
            print("No outputs generated.")
            return 1
        print(f"\nDone! Generated {len(paths)} file(s):\n")
        for p in paths:
            print(f"  {p.name}")
        open_generated(paths)
        return 0

    if command == "process":
        input_file = Path(args.input_file).expanduser().resolve()
        if not input_file.exists():
            print(f"\nERROR: input file not found: {input_file}")
            return 2
        print(f"\nProcessing: {input_file.name}")
        doc = Document.from_file(input_file)
        paths = doc.process(base_dir=str(base_dir), formats=args.formats)
        if not paths:
            print("No outputs generated.")
            return 1
        print(f"\nDone! Generated {len(paths)} file(s):\n")
        for p in paths:
            print(f"  {p.name}")
        open_generated(paths)
        return 0

    interactive_mode(base_dir, parser)
    return 0


def interactive_mode(base_dir: Path, parser: argparse.ArgumentParser) -> int:
    files = list_raw_files(base_dir)
    if not files:
        print(f"\nNo supported files found in {base_dir / 'bronze'}/")
        print("Place .csv, .txt, .pdf, .json, .jsonl, or .zip files there and try again.")
        return 1

    while True:
        print_file_menu(files)
        input_file = ask_file_choice(files)
        if input_file is None:
            return 0
        mode = ask_mode()
        fmt_list = ask_formats()
        action = "Converting" if mode == "convert" else "Processing"
        print(f"\n{action}: {input_file.name}")
        doc = Document.from_file(input_file)
        if mode == "convert":
            out_dir = base_dir / "output"
            out_dir.mkdir(parents=True, exist_ok=True)
            paths = []
            for fmt in fmt_list or ["csv"]:
                out = out_dir / f"converted_{input_file.stem}.{fmt}"
                result = doc.export(fmt, output_path=out)
                if isinstance(result, Path):
                    paths.append(result)
        else:
            paths = doc.process(base_dir=str(base_dir), formats=fmt_list)
        if not paths:
            print("No outputs generated (unsupported file type or empty input).")
            return 1
        print(f"\nDone! Generated {len(paths)} file(s):\n")
        for p in paths:
            print(f"  {p.name}")
        open_generated(paths)
        print()
        print("=" * 60)
        print("  Transform another file?")
        print("=" * 60)
        print()
        print("  1. Yes, choose another file")
        print("  2. No, finish")
        print()
        again = input("Select (1 or 2): ").strip()
        if again != "1":
            break
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
