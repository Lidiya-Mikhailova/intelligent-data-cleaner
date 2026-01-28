from __future__ import annotations

import argparse
from pathlib import Path

from src.core.cleaner import IntelligentDataCleaner, OutputFormats
from src.io.opener import open_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intelligent-data-cleaner",
        description="Clean, normalize and deduplicate raw data files.",
    )

    # ВАЖНО: входной файл
    parser.add_argument(
        "input_file",
        type=str,
        help="Path to input file (.csv/.txt/.pdf/.json/.jsonl).",
    )

    parser.add_argument(
        "--base-dir",
        type=str,
        default=".",
        help="Project base directory (default: current folder).",
    )

    parser.add_argument(
        "--formats",
        nargs="*",
        default=None,
        help=(
            "Which outputs to generate. Examples: "
            "csv safe_csv xlsx txt pdf json jsonl. "
            "If omitted -> generate all."
        ),
    )

    parser.add_argument(
        "--open",
        action="store_true",
        help="Open generated files after saving (only the selected formats).",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    input_file = Path(args.input_file).expanduser().resolve()

    if not input_file.exists():
        print(f"ERROR: input file not found: {input_file}")
        return 2

    formats = OutputFormats.from_iter(args.formats)

    cleaner = IntelligentDataCleaner(base_dir=base_dir)
    generated = cleaner.process_file(input_file, formats=formats)

    if not generated:
        print("No outputs generated (unsupported file type or empty input).")
        return 1

    print("Generated files:")
    for p in generated:
        print(f"- {p}")

    if args.open:
        for p in generated:
            try:
                open_file(p)
            except Exception as e:
                print(f"Could not open {p}: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())