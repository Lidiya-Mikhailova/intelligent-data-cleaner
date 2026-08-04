import pandas as pd

import src.translation.engine as engine_mod
from src.translation.engine import translate_dataframe


class _FakeEngine:
    name = "fake"

    def translate(self, text: str, target: str, source=None) -> str:
        return "TRANSLATED"


def _patch_engine(monkeypatch):
    monkeypatch.setattr(engine_mod, "get_translation_engine", lambda engine="google": _FakeEngine())


def test_translate_dataframe_translates_text_columns(monkeypatch):
    _patch_engine(monkeypatch)
    df = pd.DataFrame({"Name": ["Привет", "Мир"], "Age": [30, 25]})
    out = translate_dataframe(df, target="en")
    assert list(out["Name"]) == ["TRANSLATED", "TRANSLATED"]
    assert list(out["Age"]) == [30, 25]


def test_translate_dataframe_explicit_columns(monkeypatch):
    _patch_engine(monkeypatch)
    df = pd.DataFrame({"Name": ["Привет", "Мир"], "Age": [30, 25]})
    out = translate_dataframe(df, target="en", columns=["Age"])
    assert list(out["Age"]) == ["TRANSLATED", "TRANSLATED"]
    assert list(out["Name"]) == ["Привет", "Мир"]


def test_translate_dataframe_empty_values_skipped(monkeypatch):
    _patch_engine(monkeypatch)
    df = pd.DataFrame({"Name": ["", "Мир", None]})
    out = translate_dataframe(df, target="en")
    assert out["Name"].tolist()[0] == ""


def test_translate_dataframe_missing_column(monkeypatch):
    _patch_engine(monkeypatch)
    df = pd.DataFrame({"Name": ["Привет"]})
    out = translate_dataframe(df, target="en", columns=["Nope"])
    assert out["Name"].tolist() == ["Привет"]


# GoogleTranslateEngine


class _FakeTranslator:
    def __init__(self, source, target):
        self.source = source
        self.target = target

    def translate(self, text):
        return "TRANSLATED"


class _RaisingTranslator:
    def __init__(self, source, target):
        pass

    def translate(self, text):
        raise RuntimeError("network down")


def test_google_engine_translate_success(monkeypatch):
    monkeypatch.setattr(engine_mod, "GoogleTranslator", _FakeTranslator)
    monkeypatch.setattr(engine_mod, "DEEP_TRANSLATOR_AVAILABLE", True)
    engine = engine_mod.GoogleTranslateEngine()
    assert engine.name == "google"
    assert engine.translate("hello", "ru") == "TRANSLATED"
    assert engine.translate("hello", "ru", source="en") == "TRANSLATED"


def test_google_engine_translate_empty_text(monkeypatch):
    monkeypatch.setattr(engine_mod, "DEEP_TRANSLATOR_AVAILABLE", True)
    engine = engine_mod.GoogleTranslateEngine()
    assert engine.translate("", "ru") == ""
    assert engine.translate("   ", "ru") == "   "


def test_google_engine_translate_not_available(monkeypatch):
    monkeypatch.setattr(engine_mod, "DEEP_TRANSLATOR_AVAILABLE", False)
    engine = engine_mod.GoogleTranslateEngine()
    assert engine.translate("hello", "ru") == "hello"


def test_google_engine_translate_failure_returns_original(monkeypatch):
    monkeypatch.setattr(engine_mod, "GoogleTranslator", _RaisingTranslator)
    monkeypatch.setattr(engine_mod, "DEEP_TRANSLATOR_AVAILABLE", True)
    engine = engine_mod.GoogleTranslateEngine()
    assert engine.translate("hello", "ru") == "hello"


# NullTranslationEngine


def test_null_engine_returns_text():
    engine = engine_mod.NullTranslationEngine()
    assert engine.translate("hello", "en") == "hello"
    assert engine.name == "null"


# get_translation_engine / translate_text


def test_get_translation_engine_google_available(monkeypatch):
    monkeypatch.setattr(engine_mod, "DEEP_TRANSLATOR_AVAILABLE", True)
    assert isinstance(engine_mod.get_translation_engine("google"), engine_mod.GoogleTranslateEngine)


def test_get_translation_engine_fallback(monkeypatch):
    monkeypatch.setattr(engine_mod, "DEEP_TRANSLATOR_AVAILABLE", False)
    assert isinstance(engine_mod.get_translation_engine("google"), engine_mod.NullTranslationEngine)
    assert isinstance(engine_mod.get_translation_engine("other"), engine_mod.NullTranslationEngine)


def test_translate_text_uses_engine(monkeypatch):
    _patch_engine(monkeypatch)
    assert engine_mod.translate_text("hello", target="en") == "TRANSLATED"
