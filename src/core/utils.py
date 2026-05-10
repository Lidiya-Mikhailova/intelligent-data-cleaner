from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def cleanup_output(output_dir: Path, max_files: int = 10, max_size_mb: float = 100.0) -> None:
    """
    Clean up output directory by keeping only the most recent files
    and ensuring total size does not exceed the limit.
    """
    if not output_dir.exists():
        return

    files = sorted(
        output_dir.iterdir(),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    total_size = sum(f.stat().st_size for f in files if f.is_file())
    total_size_mb = total_size / (1024 * 1024)

    files_to_delete: list[Path] = []

    if len(files) > max_files:
        files_to_delete.extend(files[max_files:])

    if total_size_mb > max_size_mb:
        current_size = 0
        for f in files:
            if f in files_to_delete:
                continue
            current_size += f.stat().st_size
            if current_size / (1024 * 1024) > max_size_mb:
                files_to_delete.append(f)

    for f in set(files_to_delete):
        try:
            f.unlink()
            logger.info("Cleaned up old file: %s", f.name)
        except Exception as e:
            logger.warning("Failed to delete %s: %s", f.name, e)
