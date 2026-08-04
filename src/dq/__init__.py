from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.normalization.base import ProcessingStage, is_text_dtype

if TYPE_CHECKING:
    from src.document import Document

logger = logging.getLogger(__name__)

try:
    import pyarrow as pa

    _ARROW_STR: Optional[pd.api.extensions.ExtensionDtype] = pd.ArrowDtype(pa.string())
except ImportError:  # pragma: no cover
    _ARROW_STR = None


def _str_col(col: pd.Series) -> pd.Series:
    """Object-dtype column as a string Series (Arrow-backed when available)."""
    s = col.astype(str)
    if _ARROW_STR is not None:
        return s.astype(_ARROW_STR)
    return s


# Models


@dataclass
class DQCheckResult:
    check_name: str
    category: str
    status: str
    severity: str
    message: str = ""
    details: Dict[str, Any] = dc_field(default_factory=dict)


DQ_COLUMNS = ["_dq_score", "_dq_status", "_dq_checks"]


# Check helpers


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
    return [c for c in df.columns if is_text_dtype(df[c].dtype)]


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


_PASS_JSON_CACHE: Dict[Tuple[str, str], str] = {}


def _row_checks_json(row_results: List[Dict[str, Any]]) -> str:
    cache = _PASS_JSON_CACHE
    parts: List[str] = []
    for d in row_results:
        if d.get("status") == "pass":
            key = (d["check_name"], d["category"])
            encoded = cache.get(key)
            if encoded is None:
                encoded = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
                cache[key] = encoded
            parts.append(encoded)
        else:
            parts.append(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
    return "[" + ",".join(parts) + "]"


# Checks


def _empty_mask(col: pd.Series) -> pd.Series:
    """Vectorized "missing or empty string" mask for a column."""
    return col.isna() | col.astype(str).str.strip().eq("")


def check_schema(
    df: pd.DataFrame,
    required_fields: Optional[List[str]] = None,
) -> pd.Series:
    required_fields = required_fields or []
    per_row: List[List[Dict[str, Any]]] = [[] for _ in range(len(df))]
    for field in required_fields:
        if field not in df.columns:
            col = pd.Series([None] * len(df), index=df.index)
        else:
            col = df[field]
        empty = _empty_mask(col)
        for i in np.flatnonzero(empty.to_numpy()):
            per_row[int(i)].append(
                _fail_result(
                    "required_fields",
                    "schema",
                    f"Required field '{field}' is missing or empty",
                    {"field": field},
                )
            )
    for i, row_results in enumerate(per_row):
        if not row_results:
            per_row[i] = [_pass_result("required_fields", "schema")]
    return pd.Series(per_row, index=df.index)


_DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    re.compile(r"^\d{2}\.\d{2}\.\d{4}$"),
]
_DATE_COMBINED = re.compile("|".join(p.pattern for p in _DATE_PATTERNS))


def check_types(
    df: pd.DataFrame, numeric_fields: Optional[List[str]] = None, date_fields: Optional[List[str]] = None
) -> pd.Series:
    per_row: List[List[Dict[str, Any]]] = [[] for _ in range(len(df))]
    for field in numeric_fields or []:
        if field not in df.columns:
            continue
        col = df[field]
        col_arr = col.to_numpy()
        sval = _str_col(col).str.strip()
        nonempty_np = ~(
            col.isna().to_numpy() | (sval == "").to_numpy() | (sval == "NA").to_numpy()
        )
        numeric_ok_np = pd.to_numeric(col, errors="coerce").notna().to_numpy()
        for i in np.flatnonzero(nonempty_np & ~numeric_ok_np):
            per_row[int(i)].append(
                _warn_result(
                    "field_types",
                    "type",
                    f"Field '{field}' is not a valid number",
                    {"field": field, "value": str(col_arr[i])},
                )
            )
    for field in date_fields or []:
        if field not in df.columns:
            continue
        col = df[field]
        col_arr = col.to_numpy()
        sval = _str_col(col).str.strip()
        nonempty_np = ~(
            col.isna().to_numpy() | (sval == "").to_numpy() | (sval == "NA").to_numpy()
        )
        pattern_match = sval.str.match(_DATE_COMBINED.pattern).fillna(False)
        parsed = pd.to_datetime(sval, errors="coerce")
        for i in np.flatnonzero(nonempty_np & ~pattern_match.to_numpy() & parsed.isna().to_numpy()):
            per_row[int(i)].append(
                _warn_result(
                    "field_types",
                    "type",
                    f"Field '{field}' is not a valid date",
                    {"field": field, "value": str(col_arr[i])},
                )
            )
    for i, row_results in enumerate(per_row):
        if not row_results:
            per_row[i] = [_pass_result("field_types", "type")]
    return pd.Series(per_row, index=df.index)


def check_nulls(df: pd.DataFrame, critical_fields: Optional[List[str]] = None) -> pd.Series:
    per_row: List[List[Dict[str, Any]]] = [[] for _ in range(len(df))]
    for field in critical_fields or []:
        if field not in df.columns:
            continue
        empty = _empty_mask(df[field])
        for i in np.flatnonzero(empty.to_numpy()):
            per_row[int(i)].append(
                _fail_result("critical_nulls", "null", f"Critical field '{field}' is empty", {"field": field})
            )
    if len(df) and len(df.columns):
        empty_cols = [
            df[c].isna().to_numpy() | _str_col(df[c]).str.strip().eq("").to_numpy()
            for c in df.columns
        ]
        empty_matrix = np.column_stack(empty_cols)
        ratio = empty_matrix.sum(axis=1) / len(df.columns)
        for i in np.flatnonzero(ratio > 0.8):
            per_row[int(i)].append(
                _warn_result(
                    "suspicious_empty",
                    "null",
                    "Record is >80% empty",
                    {"empty_ratio": round(float(ratio[i]), 2)},
                )
            )
    for i, row_results in enumerate(per_row):
        if not any(r["check_name"] in ("critical_nulls", "suspicious_empty") for r in row_results):
            per_row[i].insert(0, _pass_result("critical_nulls", "null"))
    return pd.Series(per_row, index=df.index)


_OCR_NOISE_RE = re.compile(r"[^a-zA-Zа-яА-ЯёЁ0-9\s\.,;:!?\-()@#]+")
_OCR_NOISE_CHAR_RE = re.compile(r"[^a-zA-Zа-яА-ЯёЁ0-9\s\.,;:!?\-()@#]")
_OCR_GARBAGE_RE = re.compile(r"[$%^&*+=~{}|`<>]+")


def check_ocr_quality(df: pd.DataFrame, text_fields: Optional[List[str]] = None) -> pd.Series:
    fields = text_fields or _text_cols(df)
    per_row: List[List[Dict[str, Any]]] = [[] for _ in range(len(df))]
    for field in fields:
        if field not in df.columns:
            continue
        col = _str_col(df[field])
        is_empty = col.isin(["nan", ""])
        nonempty_arr = (~is_empty).to_numpy()
        safe = col.where(~is_empty, "")
        safe_arr = safe.to_numpy(dtype=str, na_value="")
        noise_len = safe.str.count(_OCR_NOISE_CHAR_RE.pattern)
        total_len = safe.str.len()
        ratio = (noise_len / total_len.where(total_len > 0, 1)).to_numpy()
        for i in np.flatnonzero(nonempty_arr & (ratio > 0.3)):
            per_row[int(i)].append(
                _warn_result(
                    "ocr_noise_ratio",
                    "ocr_quality",
                    f"High noise ratio in '{field}': {ratio[i]:.0%}",
                    {"field": field, "noise_ratio": round(float(ratio[i]), 2)},
                )
            )
        has_garbage = safe.str.contains(_OCR_GARBAGE_RE.pattern)
        for i in np.flatnonzero(nonempty_arr & has_garbage.to_numpy()):
            per_row[int(i)].append(
                _fail_result(
                    "ocr_corrupted",
                    "ocr_quality",
                    f"Corrupted OCR output in '{field}'",
                    {"field": field, "garbage_chars": _OCR_GARBAGE_RE.findall(safe_arr[i])[:5]},
                )
            )
    for i, row_results in enumerate(per_row):
        if not any(r["check_name"].startswith("ocr_") for r in row_results):
            per_row[i].append(_pass_result("ocr_quality", "ocr_quality"))
    return pd.Series(per_row, index=df.index)


def check_dedup_quality(df: pd.DataFrame, key_fields: Optional[List[str]] = None) -> pd.Series:
    fields = key_fields or _text_cols(df)
    per_row: List[List[Dict[str, Any]]] = [[] for _ in range(len(df))]
    if len(df):
        if fields:
            norm = {c: _str_col(df[c]).str.strip().str.lower() for c in fields}
            keys_arr = norm[fields[0]].to_numpy(dtype=str, na_value="")
            for col in fields[1:]:
                keys_arr = np.char.add(
                    np.char.add(keys_arr, "|"),
                    norm[col].to_numpy(dtype=str, na_value=""),
                )
            keys = pd.Series(keys_arr, index=df.index)
        else:
            keys = pd.Series([""] * len(df), index=df.index)
        positions = pd.Series(np.arange(len(keys)), index=keys.index)
        first_pos_arr = positions.groupby(keys).transform("min").to_numpy()
        dup_mask_arr = keys.duplicated(keep="first").to_numpy()
        for i in np.flatnonzero(dup_mask_arr):
            per_row[int(i)].append(
                _warn_result(
                    "dedup_collision",
                    "dedup_quality",
                    "Exact duplicate detected after dedup stage",
                    {"original_idx": int(first_pos_arr[i]), "duplicate_idx": int(i)},
                )
            )
    for i, row_results in enumerate(per_row):
        if not row_results:
            per_row[i].append(_pass_result("dedup_quality", "dedup_quality"))
    return pd.Series(per_row, index=df.index)


def check_translation_quality(df: pd.DataFrame, text_fields: Optional[List[str]] = None) -> pd.Series:
    fields = text_fields or _text_cols(df)
    replacement_char = "\ufffd"
    per_row: List[List[Dict[str, Any]]] = [[] for _ in range(len(df))]
    for field in fields:
        if field not in df.columns:
            continue
        col = _str_col(df[field])
        nonempty_arr = (~col.isin(["nan", ""])).to_numpy()
        has_replacement = col.str.contains(replacement_char, regex=False)
        for i in np.flatnonzero(nonempty_arr & has_replacement.to_numpy()):
            per_row[int(i)].append(
                _fail_result(
                    "translation_broken_unicode",
                    "translation_quality",
                    f"Broken unicode in '{field}'",
                    {"field": field},
                )
            )
    for i, row_results in enumerate(per_row):
        if not any(r["check_name"].startswith("translation_") for r in row_results):
            per_row[i].append(_pass_result("translation_quality", "translation_quality"))
    return pd.Series(per_row, index=df.index)


_MOJIBAKE_RE = re.compile(r"[\x80-\xBF]|Ã[˜Â]|Ãƒ[‚—]|Â[°±²³´µ¶·¸¹º»¼½¾¿]")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def check_normalization_quality(df: pd.DataFrame, text_fields: Optional[List[str]] = None) -> pd.Series:
    fields = text_fields or _text_cols(df)
    per_row: List[List[Dict[str, Any]]] = [[] for _ in range(len(df))]
    for field in fields:
        if field not in df.columns:
            continue
        col = _str_col(df[field])
        nonempty_arr = (~col.isin(["nan", ""])).to_numpy()
        safe_arr = col.to_numpy(dtype=str, na_value="")
        has_mojibake = col.str.contains(_MOJIBAKE_RE.pattern)
        for i in np.flatnonzero(nonempty_arr & has_mojibake.to_numpy()):
            per_row[int(i)].append(
                _warn_result(
                    "normalization_mojibake",
                    "normalization_quality",
                    f"Possible mojibake in '{field}'",
                    {"field": field, "sample": safe_arr[i][:50]},
                )
            )
        has_control = col.str.contains(_CONTROL_CHARS_RE.pattern)
        for i in np.flatnonzero(nonempty_arr & has_control.to_numpy()):
            per_row[int(i)].append(
                _warn_result(
                    "normalization_control_chars",
                    "normalization_quality",
                    f"Control characters in '{field}'",
                    {"field": field, "chars": [hex(ord(c)) for c in _CONTROL_CHARS_RE.findall(safe_arr[i])[:5]]},
                )
            )
    for i, row_results in enumerate(per_row):
        if not any(r["check_name"].startswith("normalization_") for r in row_results):
            per_row[i].append(_pass_result("normalization_quality", "normalization_quality"))
    return pd.Series(per_row, index=df.index)


# DQ Service


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
                per_row_results = check_fn(work_df, **kwargs).tolist()
                for i, results in enumerate(per_row_results):
                    all_results[i].extend(results)
            except Exception as e:
                logger.warning("DQ check %s failed: %s", check_fn.__name__, e)
        scores: List[float] = [0.0] * len(all_results)
        statuses: List[str] = [""] * len(all_results)
        checks_json: List[str] = [""] * len(all_results)
        for i, row_results in enumerate(all_results):
            score = _score_from_results(row_results)
            scores[i] = score
            statuses[i] = _status_from_score(score)
            checks_json[i] = _row_checks_json(row_results)
        result = strip_dq_columns(df.copy())
        result[DQ_COLUMNS[0]] = pd.Series(scores, index=result.index)
        result[DQ_COLUMNS[1]] = pd.Series(statuses, index=result.index)
        result[DQ_COLUMNS[2]] = pd.Series(checks_json, index=result.index)
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


# DQStage


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
