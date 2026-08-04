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
