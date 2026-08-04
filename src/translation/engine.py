from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import pandas as pd

from src.normalization.base import is_text_dtype

logger = logging.getLogger(__name__)

try:
    from deep_translator import GoogleTranslator

    DEEP_TRANSLATOR_AVAILABLE = True
except ImportError:
    DEEP_TRANSLATOR_AVAILABLE = False


class TranslationEngine(ABC):
    @abstractmethod
    def translate(self, text: str, target: str, source: Optional[str] = None) -> str:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class GoogleTranslateEngine(TranslationEngine):
    def __init__(self):
        self._translator = None
        if DEEP_TRANSLATOR_AVAILABLE:
            self._translator = GoogleTranslator

    def translate(self, text: str, target: str, source: Optional[str] = None) -> str:
        if not text or not text.strip():
            return text
        if not DEEP_TRANSLATOR_AVAILABLE:
            logger.warning("deep-translator not available, returning original text")
            return text
        try:
            t = GoogleTranslator(source=source or "auto", target=target)
            return t.translate(text)
        except Exception as e:
            logger.warning("Translation failed: %s", e)
            return text

    @property
    def name(self) -> str:
        return "google"


class NullTranslationEngine(TranslationEngine):
    def translate(self, text: str, target: str, source: Optional[str] = None) -> str:
        return text

    @property
    def name(self) -> str:
        return "null"


def get_translation_engine(engine: str = "google") -> TranslationEngine:
    if engine == "google" and DEEP_TRANSLATOR_AVAILABLE:
        return GoogleTranslateEngine()
    return NullTranslationEngine()


def translate_text(text: str, target: str = "en", source: Optional[str] = None) -> str:
    engine = get_translation_engine("google")
    return engine.translate(text, target, source)


def translate_dataframe(
    df: pd.DataFrame,
    target: str = "en",
    source: Optional[str] = None,
    columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    cols_to_translate = columns or [c for c in df.columns if is_text_dtype(df[c].dtype)]
    engine = get_translation_engine("google")
    df = df.copy()

    for col in cols_to_translate:
        if col not in df.columns:
            continue
        logger.info("Translating column: %s -> %s", col, target)
        df[col] = df[col].astype(str).apply(
            lambda x: engine.translate(x, target, source) if x and x.strip() else x
        )

    return df
