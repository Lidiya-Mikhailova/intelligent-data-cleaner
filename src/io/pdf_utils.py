from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass(frozen=True)
class PdfScanReport:
    """
    Lightweight scan detection report.

    A PDF is considered "scanned" when most pages have too little extractable text.
    """
    total_pages: int
    scanned_pages: int
    scanned_ratio: float
    is_scanned: bool


def detect_scanned_pdf(
    path: Path,
    *,
    min_chars_per_page: int = 30,
    min_words_per_page: int = 3,
    scanned_ratio_threshold: float = 0.6,
) -> PdfScanReport:
    """
    Detect whether a PDF is likely scanned (image-based) vs text-based.

    Heuristic per page:
      - Extract text (pdfplumber).
      - If text is very short AND has too few words -> scanned-like page.

    Final decision:
      - scanned_pages / total_pages >= scanned_ratio_threshold -> is_scanned = True
    """
    total_pages = 0
    scanned_pages = 0

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            total_pages += 1
            text = (page.extract_text() or "").strip()

            word_count = len(text.split())
            is_scanned_like = (len(text) < min_chars_per_page) and (word_count < min_words_per_page)

            if is_scanned_like:
                scanned_pages += 1

    ratio = (scanned_pages / total_pages) if total_pages else 1.0
    is_scanned = ratio >= scanned_ratio_threshold

    return PdfScanReport(
        total_pages=total_pages,
        scanned_pages=scanned_pages,
        scanned_ratio=ratio,
        is_scanned=is_scanned,
    )