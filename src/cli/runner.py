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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    cleaner = IntelligentDataCleaner(base_dir=base_dir)

    formats = OutputFormats.from_iter(args.formats)

    raw_dir = base_dir / "raw_data"
    for file in raw_dir.glob("*.*"):
        if file.name.startswith("."):
            continue

        generated = cleaner.process_file(file, formats=formats)

        if args.open:
            for p in generated:
                open_file(p)


if __name__ == "__main__":
    main()