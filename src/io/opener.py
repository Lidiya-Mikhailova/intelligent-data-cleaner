import os
import platform
import subprocess
from pathlib import Path


def open_file(path: Path) -> None:
    """
    Open a file with a sensible default app.

    On macOS, JSON/JSONL are opened with TextEdit to avoid
    "No application knows how to open URL" errors.
    """
    system = platform.system()
    suffix = path.suffix.lower()

    if system == "Darwin":
        # Force a text editor for text-like outputs
        if suffix in {".txt", ".json", ".jsonl", ".csv"}:
            subprocess.run(["open", "-a", "TextEdit", str(path)], check=False)
        else:
            subprocess.run(["open", str(path)], check=False)

    elif system == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]

    elif system == "Linux":
        subprocess.run(["xdg-open", str(path)], check=False)