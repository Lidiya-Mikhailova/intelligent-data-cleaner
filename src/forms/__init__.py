# Import concrete extractors to trigger @register_form decorators
from src.forms import f1099, w2, w4
from src.forms.base import BaseFormExtractor
from src.forms.registry import FORM_REGISTRY, detect_form, extract_form

__all__ = [
    "BaseFormExtractor",
    "FORM_REGISTRY",
    "detect_form",
    "extract_form",
    "f1099",
    "w2",
    "w4",
]
