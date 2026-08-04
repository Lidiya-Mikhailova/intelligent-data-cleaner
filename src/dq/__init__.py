from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import pandas as pd

from src.normalization.base import ProcessingStage

if TYPE_CHECKING:
    from src.document import Document

logger = logging.getLogger(__name__)


# ── Models ──────────────────────────────────────────────────────────────────────


@dataclass
class DQCheckResult:
    check_name: str
    category: str
    status: str
    severity: str
    message: str = ""
    details: Dict[str, Any] = dc_field(default_factory=dict)


DQ_COLUMNS = ["_dq_score", "_dq_status", "_dq_checks"]


# ── Check helpers ───────────────────────────────────────────────────────────────


def _result(
    check_name: str,
    category: str,
    status: str,
    severity: str,
    message: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "check_name": check_name,
        "category": category,
        "status": status,
        "severity": severity,
        "message": message,
        "details": details or {},
    }


def _pass_result(check_name: str, category: str) -> Dict[str, Any]:
    return _result(check_name, category, "pass", "info")


def _warn_result(
    check_name: str, category: str, message: str, details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return _result(check_name, category, "warn", "warn", message, details)


def _fail_result(
    check_name: str, category: str, message: str, details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return _result(check_name, category, "fail", "error", message, details)


def _text_cols(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns if df[c].dtype == object]


def _score_from_results(results: List[Dict[str, Any]]) -> float:
    if not results:
        return 0.0
    weights = {"info": 0.0, "warn": 0.3, "error": 0.6, "critical": 1.0}
    max_severity = 0.0
    for r in results:
        if r["status"] in ("fail", "warn"):
            sev = weights.get(r.get("severity", "info"), 0.0)
            if sev > max_severity:
                max_severity = sev
    return max_severity


def _status_from_score(score: float) -> str:
    if score >= 0.6:
        return "fail"
    if score >= 0.3:
        return "warn"
    return "pass"


# ── Checks ──────────────────────────────────────────────────────────────────────


def check_schema(
    df: pd.DataFrame,
    required_fields: Optional[List[str]] = None,
) -> pd.Series:
    results: List[List[Dict[str, Any]]] = []
    for _, row in df.iterrows():
        row_results: List[Dict[str, Any]] = []
        if required_fields:
            for field in required_fields:
                val = row.get(field)
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    row_results.append(
                        _fail_result(
                            "required_fields",
                            "schema",
                            f"Required field '{field}' is missing or empty",
                            {"field": field},
                        )
                    )
        if not row_results:
            row_results.append(_pass_result("required_fields", "schema"))
        results.append(row_results)
    return pd.Series(results, index=df.index)


def check_types(
    df: pd.DataFrame, numeric_fields: Optional[List[str]] = None, date_fields: Optional[List[str]] = None
) -> pd.Series:
    date_patterns = [
        re.compile(r"^\d{4}-\d{2}-\d{2}$"),
        re.compile(r"^\d{2}/\d{2}/\d{4}$"),
        re.compile(r"^\d{2}\.\d{2}\.\d{4}$"),
    ]
    results: List[List[Dict[str, Any]]] = []
    for _, row in df.iterrows():
        row_results: List[Dict[str, Any]] = []
        if numeric_fields:
            for field in numeric_fields:
                val = row.get(field)
                if val is not None and val != "" and val != "NA":
                    try:
                        float(val)
                    except (ValueError, TypeError):
                        row_results.append(
                            _warn_result(
                                "field_types",
                                "type",
                                f"Field '{field}' is not a valid number",
                                {"field": field, "value": str(val)},
                            )
                        )
        if date_fields:
            for field in date_fields:
                val = row.get(field)
                if val is not None and val != "" and val != "NA":
                    sval = str(val).strip()
                    if not any(p.match(sval) for p in date_patterns):
                        try:
                            pd.to_datetime(sval, errors="coerce")
                            if pd.isna(pd.to_datetime(sval, errors="coerce")):
                                raise ValueError
                        except Exception:
                            row_results.append(
                                _warn_result(
                                    "field_types",
                                    "type",
                                    f"Field '{field}' is not a valid date",
                                    {"field": field, "value": sval},
                                )
                            )
        if not row_results:
            row_results.append(_pass_result("field_types", "type"))
        results.append(row_results)
    return pd.Series(results, index=df.index)


def check_nulls(df: pd.DataFrame, critical_fields: Optional[List[str]] = None) -> pd.Series:
    results: List[List[Dict[str, Any]]] = []
    for _, row in df.iterrows():
        row_results: List[Dict[str, Any]] = []
        if critical_fields:
            for field in critical_fields:
                val = row.get(field)
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    row_results.append(
                        _fail_result("critical_nulls", "null", f"Critical field '{field}' is empty", {"field": field})
                    )
        empty_count = sum(1 for v in row if v is None or (isinstance(v, str) and v.strip() == ""))
        total = len(row)
        if total > 0 and empty_count / total > 0.8:
            row_results.append(
                _warn_result(
                    "suspicious_empty", "null", "Record is >80% empty", {"empty_ratio": round(empty_count / total, 2)}
                )
            )
        if not any(r["check_name"] in ("critical_nulls", "suspicious_empty") for r in row_results):
            row_results.insert(0, _pass_result("critical_nulls", "null"))
        results.append(row_results)
    return pd.Series(results, index=df.index)


def check_ocr_quality(df: pd.DataFrame, text_fields: Optional[List[str]] = None) -> pd.Series:
    fields = text_fields or _text_cols(df)
    noise_pattern = re.compile(r"[^a-zA-Zа-яА-ЯёЁ0-9\s\.,;:!?\-()@#]+")
    garbage_pattern = re.compile(r"[$%^&*+=~{}|`<>]+")
    results: List[List[Dict[str, Any]]] = []
    for _, row in df.iterrows():
        row_results: List[Dict[str, Any]] = []
        for field in fields:
            val = str(row.get(field, ""))
            if not val or val == "nan":
                continue
            noise_chars = noise_pattern.findall(val)
            noise_ratio = sum(len(c) for c in noise_chars) / max(len(val), 1)
            if noise_ratio > 0.3:
                row_results.append(
                    _warn_result(
                        "ocr_noise_ratio",
                        "ocr_quality",
                        f"High noise ratio in '{field}': {noise_ratio:.0%}",
                        {"field": field, "noise_ratio": round(noise_ratio, 2)},
                    )
                )
            garbage_chars = garbage_pattern.findall(val)
            if garbage_chars:
                row_results.append(
                    _fail_result(
                        "ocr_corrupted",
                        "ocr_quality",
                        f"Corrupted OCR output in '{field}'",
                        {"field": field, "garbage_chars": garbage_chars[:5]},
                    )
                )
            if len(val.strip()) == 0:
                row_results.append(
                    _warn_result(
                        "ocr_unreadable", "ocr_quality", f"Empty text in '{field}'", {"field": field, "length": 0}
                    )
                )
        if not any(r["check_name"].startswith("ocr_") for r in row_results):
            row_results.append(_pass_result("ocr_quality", "ocr_quality"))
        results.append(row_results)
    return pd.Series(results, index=df.index)


def check_dedup_quality(df: pd.DataFrame, key_fields: Optional[List[str]] = None) -> pd.Series:
    fields = key_fields or _text_cols(df)
    results: List[List[Dict[str, Any]]] = []
    seen_keys: Dict[str, int] = {}
    for idx, (_, row) in enumerate(df.iterrows()):
        row_results: List[Dict[str, Any]] = []
        key_parts = []
        for f in fields:
            val = str(row.get(f, "")).strip().lower()
            key_parts.append(val)
        row_key = "|".join(key_parts)
        if row_key in seen_keys:
            row_results.append(
                _warn_result(
                    "dedup_collision",
                    "dedup_quality",
                    "Exact duplicate detected after dedup stage",
                    {"original_idx": seen_keys[row_key], "duplicate_idx": idx},
                )
            )
        else:
            seen_keys[row_key] = idx
        if not row_results:
            row_results.append(_pass_result("dedup_quality", "dedup_quality"))
        results.append(row_results)
    return pd.Series(results, index=df.index)


def check_translation_quality(df: pd.DataFrame, text_fields: Optional[List[str]] = None) -> pd.Series:
    fields = text_fields or _text_cols(df)
    replacement_char = "\ufffd"
    results: List[List[Dict[str, Any]]] = []
    for _, row in df.iterrows():
        row_results: List[Dict[str, Any]] = []
        for field in fields:
            val = str(row.get(field, ""))
            if not val or val == "nan":
                continue
            if replacement_char in val:
                row_results.append(
                    _fail_result(
                        "translation_broken_unicode",
                        "translation_quality",
                        f"Broken unicode in '{field}'",
                        {"field": field},
                    )
                )
            if len(val.strip()) == 0:
                row_results.append(
                    _warn_result(
                        "translation_empty", "translation_quality", f"Empty translation in '{field}'", {"field": field}
                    )
                )
        if not any(r["check_name"].startswith("translation_") for r in row_results):
            row_results.append(_pass_result("translation_quality", "translation_quality"))
        results.append(row_results)
    return pd.Series(results, index=df.index)


def check_normalization_quality(df: pd.DataFrame, text_fields: Optional[List[str]] = None) -> pd.Series:
    fields = text_fields or _text_cols(df)
    mojibake_pattern = re.compile(r"[\x80-\xBF]|Ã[˜Â]|Ãƒ[‚—]|Â[°±²³´µ¶·¸¹º»¼½¾¿]")
    control_chars = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
    results: List[List[Dict[str, Any]]] = []
    for _, row in df.iterrows():
        row_results: List[Dict[str, Any]] = []
        for field in fields:
            val = str(row.get(field, ""))
            if not val or val == "nan":
                continue
            if mojibake_pattern.search(val):
                row_results.append(
                    _warn_result(
                        "normalization_mojibake",
                        "normalization_quality",
                        f"Possible mojibake in '{field}'",
                        {"field": field, "sample": val[:50]},
                    )
                )
            ctrl = control_chars.findall(val)
            if ctrl:
                row_results.append(
                    _warn_result(
                        "normalization_control_chars",
                        "normalization_quality",
                        f"Control characters in '{field}'",
                        {"field": field, "chars": [hex(ord(c)) for c in ctrl[:5]]},
                    )
                )
        if not any(r["check_name"].startswith("normalization_") for r in row_results):
            row_results.append(_pass_result("normalization_quality", "normalization_quality"))
        results.append(row_results)
    return pd.Series(results, index=df.index)


# ── DQ Service ──────────────────────────────────────────────────────────────────


DEFAULT_CHECKS: List[Callable] = [
    check_schema,
    check_types,
    check_nulls,
    check_ocr_quality,
    check_dedup_quality,
    check_translation_quality,
    check_normalization_quality,
]


class DQService:
    def __init__(
        self,
        checks: Optional[List[Callable]] = None,
        check_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self._checks = checks or DEFAULT_CHECKS
        self._check_kwargs = check_kwargs or {}

    def run_all(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            clean = df.copy()
            for c in DQ_COLUMNS:
                clean[c] = pd.Series(dtype=float if c == "_dq_score" else str)
            return clean
        work_df = strip_dq_columns(df.copy())
        all_results: List[List[Dict[str, Any]]] = [[] for _ in range(len(work_df))]
        for check_fn in self._checks:
            kwargs = self._check_kwargs.get(check_fn.__name__, {})
            try:
                per_row_results = check_fn(work_df, **kwargs)
                for i, results in enumerate(per_row_results):
                    all_results[i].extend(results)
            except Exception as e:
                logger.warning("DQ check %s failed: %s", check_fn.__name__, e)
        dq_cols_data: List[Dict[str, Any]] = []
        for row_results in all_results:
            score = _score_from_results(row_results)
            status = _status_from_score(score)
            dq_cols_data.append(
                {
                    "_dq_score": score,
                    "_dq_status": status,
                    "_dq_checks": json.dumps(row_results, ensure_ascii=False, default=str),
                }
            )
        result = strip_dq_columns(df.copy())
        result[DQ_COLUMNS[0]] = pd.Series([d["_dq_score"] for d in dq_cols_data], index=result.index)
        result[DQ_COLUMNS[1]] = pd.Series([d["_dq_status"] for d in dq_cols_data], index=result.index)
        result[DQ_COLUMNS[2]] = pd.Series([d["_dq_checks"] for d in dq_cols_data], index=result.index)
        return result

    def quality_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty or DQ_COLUMNS[1] not in df.columns:
            return {"status": "no_data", "total": len(df)}
        total = len(df)
        dq_status_counts = df[DQ_COLUMNS[1]].value_counts().to_dict()
        avg_score = float(df[DQ_COLUMNS[0]].mean()) if DQ_COLUMNS[0] in df.columns else 0.0
        all_checks: List[str] = []
        for checks_json in df[DQ_COLUMNS[2]]:
            if checks_json:
                try:
                    checks = json.loads(checks_json)
                    all_checks.extend(c["check_name"] for c in checks if c["status"] != "pass")
                except (json.JSONDecodeError, TypeError):
                    pass
        issue_counts: Dict[str, int] = {}
        for name in all_checks:
            issue_counts[name] = issue_counts.get(name, 0) + 1
        return {
            "total": total,
            "avg_dq_score": round(avg_score, 3),
            "dq_status_counts": {k: int(v) for k, v in dq_status_counts.items()},
            "issue_counts": dict(sorted(issue_counts.items(), key=lambda x: -x[1])),
            "pass_rate": round(dq_status_counts.get("pass", 0) / max(total, 1), 3),
            "warn_rate": round(dq_status_counts.get("warn", 0) / max(total, 1), 3),
            "fail_rate": round(dq_status_counts.get("fail", 0) / max(total, 1), 3),
        }


def strip_dq_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in DQ_COLUMNS if c in df.columns]
    if cols:
        return df.drop(columns=cols)
    return df


# ── DQStage ─────────────────────────────────────────────────────────────────────


class DQStage(ProcessingStage):
    name = "dq"

    def __init__(
        self,
        checks: Optional[List[str]] = None,
        check_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self._checks = checks
        self._check_kwargs = check_kwargs

    def process(self, doc: Document) -> Document:
        service = DQService(
            checks=self._checks,
            check_kwargs=self._check_kwargs,
        )
        return doc.transform(
            service.run_all,
            "dq",
            {"checks": self._checks, "check_kwargs": self._check_kwargs},
        )


__all__ = [
    "DQCheckResult",
    "DQ_COLUMNS",
    "DQService",
    "DQStage",
    "strip_dq_columns",
    "check_schema",
    "check_types",
    "check_nulls",
    "check_ocr_quality",
    "check_dedup_quality",
    "check_translation_quality",
    "check_normalization_quality",
]
