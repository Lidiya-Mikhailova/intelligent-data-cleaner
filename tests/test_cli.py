import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli import _resolve_path

pytest.importorskip("typer")
from src.cli import app  # noqa: E402

runner = CliRunner()


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def csv_file(workdir):
    path = workdir / "data.csv"
    path.write_text("Name,Age\nAlice,30\nBob,25\n", encoding="utf-8")
    return path


def _write_review(output_dir, **overrides):
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_file": "data.csv",
        "pipeline_run_id": 0,
        "rows_total": 2,
        "rows_valid": 2,
        "rows_invalid": 0,
        "rows_quarantine": 0,
        "duplicates_detected": 0,
        "possible_ocr_corruption": 0,
        "null_rate": 0.0,
        "coercion_failures": 0,
        "broken_dates": 0,
        "schema_drift_detected": False,
        "suspicious_rows_count": 0,
        "stages": [],
        "quarantine_records": [],
    }
    payload.update(overrides)
    path = output_dir / "review_20260101_000000.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# _resolve_path


def test_resolve_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _resolve_path("data.csv") == (tmp_path / "data.csv").resolve()
    assert _resolve_path(str(tmp_path / "a" / "b.csv")).name == "b.csv"


# formats


def test_formats_command(workdir):
    result = runner.invoke(app, ["formats"])
    assert result.exit_code == 0
    assert "CSV, TXT, JSON" in result.output


# process


def test_process_command(csv_file, workdir):
    result = runner.invoke(app, ["process", str(csv_file)])
    assert result.exit_code == 0, result.output
    assert "valid=" in result.output
    assert (workdir / "output").exists()
    assert list((workdir / "output").glob("review_*.json"))


def test_process_with_export(csv_file, workdir):
    out = workdir / "clean.csv"
    result = runner.invoke(app, ["process", str(csv_file), "--export", "csv", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_process_export_to_bytes(csv_file, workdir):
    result = runner.invoke(app, ["process", str(csv_file), "--export", "json"])
    assert result.exit_code == 0, result.output
    assert "bytes" in result.output


def test_process_disabled_stages(csv_file, workdir):
    result = runner.invoke(
        app,
        ["process", str(csv_file), "--no-normalize", "--no-clean", "--no-deduplicate", "--no-dq"],
    )
    assert result.exit_code == 0, result.output


def test_process_with_forms(csv_file, workdir):
    result = runner.invoke(app, ["process", str(csv_file), "--forms"])
    assert result.exit_code == 0, result.output


def test_process_with_translate(csv_file, workdir, monkeypatch):
    from src.translation import engine
    from src.translation.engine import NullTranslationEngine

    monkeypatch.setattr(engine, "get_translation_engine", lambda *a, **k: NullTranslationEngine())
    result = runner.invoke(app, ["process", str(csv_file), "--translate", "en"])
    assert result.exit_code == 0, result.output


def test_process_missing_file(workdir):
    result = runner.invoke(app, ["process", "nope.csv"])
    assert result.exit_code != 0


def test_process_reports_without_preview(csv_file, workdir):
    result = runner.invoke(app, ["process", str(csv_file), "--preview"])
    assert result.exit_code == 0, result.output
    assert "Document" in result.output


# convert


def test_convert_command(csv_file, workdir):
    out = workdir / "out.json"
    result = runner.invoke(app, ["convert", str(csv_file), "--to", "json", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_convert_default_csv(csv_file, workdir):
    result = runner.invoke(app, ["convert", str(csv_file)])
    assert result.exit_code == 0, result.output


# info


def test_info_command(csv_file, workdir):
    result = runner.invoke(app, ["info", str(csv_file)])
    assert result.exit_code == 0, result.output
    assert "Name" in result.output


# review


def test_review_latest(workdir):
    _write_review(workdir / "output")
    result = runner.invoke(app, ["review"])
    assert result.exit_code == 0, result.output
    assert "DATA QUALITY REPORT" in result.output


def test_review_no_reports(workdir):
    result = runner.invoke(app, ["review"])
    assert result.exit_code == 0, result.output
    assert "No review reports found" in result.output


def test_review_from_json_path(workdir):
    path = _write_review(workdir)
    result = runner.invoke(app, ["review", str(path)])
    assert result.exit_code == 0, result.output
    assert "DATA QUALITY REPORT" in result.output


def test_review_missing_path(workdir):
    result = runner.invoke(app, ["review", str(workdir / "nope.json")])
    assert result.exit_code == 1


def test_review_non_json_path(workdir):
    path = workdir / "x.txt"
    path.write_text("hello", encoding="utf-8")
    result = runner.invoke(app, ["review", str(path)])
    assert result.exit_code == 1
    assert "Report not found" in result.output


# quarantine


def test_quarantine_list_no_reports(workdir):
    result = runner.invoke(app, ["quarantine", "list"])
    assert result.exit_code == 0, result.output
    assert "No review reports found" in result.output


def test_quarantine_list_no_records(workdir):
    _write_review(workdir / "output")
    result = runner.invoke(app, ["quarantine", "list"])
    assert result.exit_code == 0, result.output
    assert "No quarantine records" in result.output


def test_quarantine_list_with_csv(workdir):
    _write_review(workdir / "output", rows_quarantine=1)
    (workdir / "output" / "quarantine_20260101_000000.csv").write_text(
        "Name,Age,_reason,_category,_confidence\nBob,25,Missing field,missing_field,0.85\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["quarantine", "list"])
    assert result.exit_code == 0, result.output
    assert "Quarantine records: 1" in result.output
    assert "Bob" in result.output


def test_quarantine_export(workdir):
    src = workdir / "output" / "quarantine_20260101_000000.csv"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("Name,Age\nBob,25\n", encoding="utf-8")
    out = workdir / "q.csv"
    result = runner.invoke(app, ["quarantine", "export", "--source", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_quarantine_export_no_files(workdir):
    result = runner.invoke(app, ["quarantine", "export"])
    assert result.exit_code == 0, result.output
    assert "No quarantine CSVs found" in result.output


def test_quarantine_unknown_action(workdir):
    result = runner.invoke(app, ["quarantine", "bogus"])
    assert result.exit_code == 1


# fallback without typer


def test_main_without_typer(monkeypatch):
    import builtins
    import importlib

    real_import = builtins.__import__

    def _block_typer(name, *args, **kwargs):
        if name == "typer" or name.startswith("typer."):
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block_typer)
    monkeypatch.delitem(sys.modules, "src.cli", raising=False)
    cli = importlib.import_module("src.cli")

    assert cli.TYPER_AVAILABLE is False
    assert cli.app is None
    assert cli.main() == 1


def test_cli_main_module(workdir):
    import runpy

    with pytest.raises(SystemExit):
        runpy.run_module("src.cli.__main__", run_name="__main__")


def test_cli_init_main_block(workdir):
    src = Path(__file__).parent.parent / "src" / "cli" / "__init__.py"
    code = compile(src.read_text(encoding="utf-8"), str(src), "exec")
    namespace = {"__name__": "__main__", "__file__": str(src)}
    with pytest.raises(SystemExit):
        exec(code, namespace)
