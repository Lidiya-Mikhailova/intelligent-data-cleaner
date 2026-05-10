from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber
from PIL import Image

try:
    import pytesseract

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanReport:
    total_pages: int
    scanned_pages: int
    scanned_ratio: float
    is_scanned: bool


class OCREngine(ABC):
    @abstractmethod
    def image_to_text(self, image: Image.Image, lang: str = "eng+rus") -> str:
        ...

    @abstractmethod
    def name(self) -> str:
        ...


class TesseractEngine(OCREngine):
    def image_to_text(self, image: Image.Image, lang: str = "eng+rus") -> str:
        if not TESSERACT_AVAILABLE:
            logger.warning("pytesseract not available")
            return ""
        try:
            return pytesseract.image_to_string(image, lang=lang).strip()
        except Exception as e:
            logger.error("Tesseract OCR failed: %s", e)
            return ""

    def name(self) -> str:
        return "tesseract"


class PaddleOCREngine(OCREngine):
    def image_to_text(self, image: Image.Image, lang: str = "eng+rus") -> str:
        logger.warning("PaddleOCR not yet implemented, falling back to tesseract")
        return TesseractEngine().image_to_text(image, lang)

    def name(self) -> str:
        return "paddle"


def get_ocr_engine(engine: str = "tesseract") -> OCREngine:
    engines = {
        "tesseract": TesseractEngine,
        "paddle": PaddleOCREngine,
    }
    cls = engines.get(engine.lower())
    if cls is None:
        logger.warning("Unknown OCR engine %r, using tesseract", engine)
        return TesseractEngine()
    return cls()


def detect_scanned_pdf(
    path: Path,
    *,
    min_chars_per_page: int = 30,
    min_words_per_page: int = 3,
    scanned_ratio_threshold: float = 0.6,
) -> ScanReport:
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

    return ScanReport(
        total_pages=total_pages,
        scanned_pages=scanned_pages,
        scanned_ratio=ratio,
        is_scanned=is_scanned,
    )


def ocr_pdf_page(page, engine: Optional[OCREngine] = None) -> str:
    eng = engine or TesseractEngine()
    try:
        img = page.to_image(resolution=300)
        pil_image = Image.frombytes("RGB", (img.width, img.height), img.original_bytes)
        return eng.image_to_text(pil_image)
    except Exception as e:
        logger.error("OCR failed on page: %s", e)
        return ""


def read_scanned_pdf(path: Path, engine: Optional[OCREngine] = None) -> List[Dict]:
    if not TESSERACT_AVAILABLE:
        logger.warning("Cannot read scanned PDF: pytesseract not installed")
        return []

    eng = engine or TesseractEngine()
    pages_data: List[Dict] = []

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = ocr_pdf_page(page, eng)
            if text:
                pages_data.append({"page_num": i, "text": text})

    return pages_data


def ocr_image(path: Path, engine: Optional[OCREngine] = None) -> str:
    eng = engine or TesseractEngine()
    try:
        image = Image.open(path)
        return eng.image_to_text(image)
    except Exception as e:
        logger.error("Image OCR failed: %s", e)
        return ""
