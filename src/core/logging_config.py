import logging
from pathlib import Path

def setup_logging(base_dir: Path | None = None) -> None:
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

