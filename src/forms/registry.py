from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

import pandas as pd

from src.forms.base import BaseFormExtractor

logger = logging.getLogger(__name__)

FORM_REGISTRY: Dict[str, Type[BaseFormExtractor]] = {}


def register_form(name: str):
    def decorator(cls: Type[BaseFormExtractor]):
        cls.name = name
        FORM_REGISTRY[name] = cls
        logger.debug("Registered form extractor: %s", name)
        return cls

    return decorator


def detect_form(lines: List[str]) -> Optional[str]:
    text = "\n".join(lines)
    for name, cls in FORM_REGISTRY.items():
        try:
            extractor = cls()
            if extractor.detect(text):
                logger.info("Detected form type: %s", name)
                return name
        except Exception:
            continue
    return None


def extract_form(lines: List[str], form_type: str) -> pd.DataFrame:
    cls = FORM_REGISTRY.get(form_type)
    if cls is None:
        raise ValueError(f"Unknown form type: {form_type}")
    extractor = cls()
    return extractor.extract(lines)
