import pandas as pd
import pdfplumber
from pathlib import Path
from typing import Generator


def load_csv_chunks(path: Path, chunksize: int = 50000) -> Generator[pd.DataFrame, None, None]:
    """
    Load CSV or TXT file in chunks to save memory.

    Args:
        path (Path): Path to input CSV/TXT file.
        chunksize (int): Number of rows per chunk.

    Yields:
        pd.DataFrame: Next chunk of data.
    """
    for chunk in pd.read_csv(
        path,
        sep=None,
        engine="python",
        dtype=str,
        chunksize=chunksize,
        on_bad_lines="skip",
    ):
        yield chunk.fillna("")


def read_pdf_chunks(path: Path) -> Generator[pd.DataFrame, None, None]:
    """
    Read PDF file page by page and convert to DataFrame.

    Args:
        path (Path): Path to input PDF file.

    Yields:
        pd.DataFrame: DataFrame with one column 'Text' per page.
    """
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                yield pd.DataFrame({"Text": text.split("\n")})
