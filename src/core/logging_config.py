from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(base_dir: Path | None = None) -> None:
    """
    Configure project-wide logging.

    - Writes logs to: <project_root>/logs/data_cleaner.log
    - Also prints logs to console (stdout)
    - Ensures the logs/ folder exists
    """
    if base_dir is None:
        base_dir = Path.cwd()

    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "data_cleaner.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


logging.getLogger("fontTools").setLevel(logging.WARNING)