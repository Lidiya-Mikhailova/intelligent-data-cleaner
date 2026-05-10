from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def open_file(path: Path) -> bool:
    """
    Open a file with the OS default application.

    JSON and JSONL files are opened in VSCode when available.
    Returns True if the file was opened successfully, False otherwise.
    """
    system = platform.system()
    suffix = path.suffix.lower()

    try:
        if system == "Darwin":
            if suffix in {".json", ".jsonl"}:
                result = subprocess.run(
                    ["open", "-a", "Visual Studio Code", str(path)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return True

            result = subprocess.run(["open", str(path)], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  No application found to open {path.name}.")
                print(f"  File saved at: {path}")
                return False
        elif system == "Windows":
            if suffix in {".json", ".jsonl"}:
                result = subprocess.run(
                    ["code", str(path)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return True
            os.startfile(path)  # type: ignore[attr-defined]
        elif system == "Linux":
            if suffix in {".json", ".jsonl"}:
                result = subprocess.run(
                    ["code", str(path)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return True
            result = subprocess.run(["xdg-open", str(path)], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  No application found to open {path.name}.")
                print(f"  File saved at: {path}")
                return False
    except Exception as e:
        print(f"  Could not open {path.name}: {e}")
        print(f"  File saved at: {path}")
        return False

    return True
