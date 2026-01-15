import os
import platform
from pathlib import Path


def open_file(path: Path) -> None:
    """
    Open a file with the default application according to the OS.

    Args:
        path (Path): File path to open.
    """
    system = platform.system()
    if system == "Darwin":
        os.system(f'open "{path}"')
    elif system == "Windows":
        os.startfile(path)
    elif system == "Linux":
        os.system(f'xdg-open "{path}"')
