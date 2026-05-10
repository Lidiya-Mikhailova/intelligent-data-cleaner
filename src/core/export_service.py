from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Union

import pandas as pd

from src.exporters.registry import get_exporter

logger = logging.getLogger(__name__)


def export_data(
    df: pd.DataFrame,
    output_dir: Union[str, Path],
    formats: Optional[List[str]] = None,
    font_dir: Optional[Union[str, Path]] = None,
    base_name: str = "export",
) -> List[Path]:
    """Export a DataFrame to one or more file formats.

    Orchestrates exporters — this is core business logic, not storage.
    ZIP is handled as a post-processing step (wraps all generated files).
    Returns the list of generated file paths.
    """
    generated: List[Path] = []
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    has_zip = "zip" in (formats or [])
    export_formats = [f for f in (formats or []) if f != "zip"]

    for fmt in export_formats:
        kwargs = {}
        if fmt == "pdf":
            font_path = Path(font_dir) / "DejaVuSans.ttf" if font_dir else None
            if font_path and font_path.exists():
                kwargs["font_path"] = font_path
        try:
            exporter = get_exporter(fmt)
            p = output_dir / f"{base_name}{exporter.suffix}"
            result = exporter.export(df, output_path=p, **kwargs)
            if result.path:
                generated.append(result.path)
                logger.info("Exported %s -> %s", fmt, result.path.name)
        except ValueError:
            logger.warning("Unknown export format: %s", fmt)

    if has_zip and len(generated) > 1:
        from src.io.writers import save_zip

        p = output_dir / f"{base_name}.zip"
        save_zip(generated, p)
        generated.append(p)

    return generated
