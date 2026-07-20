from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


ALIASES: dict[str, list[str]] = {
    "receipt": [
        "receipt_filing", "receipt", "receipt_flag", "official_receipt",
        "has_receipt", "kind_receipt", "actual_filing", "gold_filing",
        "receipt_positive", "receipt_disclosed", "filing_receipt",
    ],
    "proxy": [
        "proxy_filing", "proxy", "proxy_flag", "disclosed", "warning_proxy",
        "predicted_disclosure", "constructed_proxy", "proxy_positive",
        "d_warning", "filing_proxy",
    ],
    "issuer": [
        "issuer", "issuer_name", "asset_manager", "manager", "fund_company",
        "management_company", "amc", "운용사", "자산운용사",
    ],
    "date": [
        "date", "trading_date", "event_date", "base_date", "business_date",
        "dt", "일자", "기준일", "발생일",
    ],
    "product": [
        "ticker", "etf_code", "product_id", "short_code", "isu_cd", "isin",
        "symbol", "종목코드", "단축코드",
    ],
    "receipt_id": [
        "acpt_no", "receipt_id", "receipt_no", "acceptance_no", "rcp_no",
        "접수번호",
    ],
    "filing_time": [
        "filing_timestamp", "disclosure_time", "receipt_time", "filing_time",
        "accepted_at", "공시시각", "접수일시",
    ],
    "title": [
        "title", "report_title", "disclosure_title", "document_title",
        "report_nm", "보고서명", "공시제목",
    ],
    "severity": [
        "severity", "abs_gap", "gap_abs", "abs_premium", "absolute_premium",
        "premium_abs", "abs_running", "running_abs", "breach_magnitude",
        "premium_discount_abs", "괴리율절대값",
    ],
    "running": [
        "running_variable", "running", "r", "rv", "distance_to_cutoff",
        "gap_minus_cutoff", "premium_minus_cutoff",
    ],
    "congestion": [
        "congestion", "event_congestion", "same_day_events", "issuer_day_events",
        "market_congestion", "filing_congestion",
    ],
    "batch": [
        "batch_filing", "is_batch", "batch", "batch_flag", "batch_disclosure",
    ],
    "batch_size": [
        "batch_size", "document_product_count", "products_per_receipt",
        "receipt_product_count", "n_products_in_document",
    ],
    "correction": [
        "correction", "is_correction", "corrected_filing", "amendment",
        "정정공시",
    ],
    "multi_product": [
        "multi_product", "is_multi_product", "multi_etf", "multiple_products",
    ],
    "episode_length": [
        "episode_length", "breach_episode_length", "spell_length", "duration",
        "consecutive_days",
    ],
    "candidate": [
        "candidate", "candidate_event", "eligible_event", "breach",
        "threshold_breach", "is_breach", "warning_eligible",
    ],
    "domestic": [
        "domestic", "is_domestic", "domestic_etf", "market_scope_domestic",
    ],
    "staleness": [
        "staleness", "staleness_hours", "nav_staleness", "stale_hours",
    ],
    "abs_ret_next1": [
        "abs_ret_next1", "abs_return_next1", "next1_abs_return",
        "abs_ret_1d", "next_day_abs_return",
    ],
    "repeat_breach_1d": [
        "repeat_breach_1d", "repeat_breach_1", "breach_next1",
        "next_day_repeat_breach",
    ],
    "repeat_breach_5d": [
        "repeat_breach_5d", "repeat_breach_5", "breach_next5",
    ],
    "gap_reversion_1": [
        "gap_reversion_1", "gap_reversion_1d", "reversion_1d",
    ],
    "gap_reversion_5": [
        "gap_reversion_5", "gap_reversion_5d", "reversion_5d",
    ],
}


@dataclass(frozen=True)
class PanelDiscovery:
    path: Path
    score: float
    columns: list[str]
    size_bytes: int


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_extract_zip(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"CRC failure in ZIP member: {bad}")
        seen: set[str] = set()
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name in seen:
                raise RuntimeError(f"Duplicate ZIP path: {name}")
            seen.add(name)
            target = (destination / name).resolve()
            if root != target and root not in target.parents:
                raise RuntimeError(f"Unsafe ZIP path traversal: {name}")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise RuntimeError(f"Symlink member is forbidden: {name}")
        zf.extractall(destination)


def deterministic_zip(source_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    root = source_dir.resolve()
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.resolve() != zip_path.resolve())
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            rel = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(rel)
            info.date_time = (2020, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes())


def _canonical(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", str(s).strip().lower())


def resolve_column(columns: Iterable[str], aliases: Iterable[str]) -> str | None:
    cols = list(columns)
    exact = {_canonical(c): c for c in cols}
    for alias in aliases:
        key = _canonical(alias)
        if key in exact:
            return exact[key]
    # conservative substring fallback: only long aliases
    for alias in aliases:
        key = _canonical(alias)
        if len(key) < 6:
            continue
        hits = [c for c in cols if key in _canonical(c) or _canonical(c) in key]
        if len(hits) == 1:
            return hits[0]
    return None


def coerce_binary(series: pd.Series, name: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype("Int64")
    numeric = pd.to_numeric(series, errors="coerce")
    nonmissing = numeric.dropna()
    if not nonmissing.empty and set(nonmissing.unique()).issubset({0, 1}):
        return numeric.round().astype("Int64")
    truthy = {
        "1", "true", "t", "yes", "y", "filed", "disclosed", "receipt",
        "공시", "있음", "해당", "발생",
    }
    falsy = {
        "0", "false", "f", "no", "n", "notfiled", "undisclosed",
        "없음", "미공시", "미해당", "미발생",
    }
    cleaned = series.astype("string").str.strip().str.lower().str.replace(r"\s+", "", regex=True)
    out = pd.Series(pd.NA, index=series.index, dtype="Int64")
    out[cleaned.isin(truthy)] = 1
    out[cleaned.isin(falsy)] = 0
    unresolved = out.isna() & series.notna()
    if unresolved.any():
        examples = series[unresolved].astype(str).value_counts().head(10).to_dict()
        raise ValueError(f"Cannot coerce {name} to binary. Examples: {examples}")
    return out


def _peek_columns(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        try:
            import pyarrow.parquet as pq
            return list(pq.ParquetFile(path).schema.names)
        except Exception:
            return list(pd.read_parquet(path).columns)
    if suffix == ".csv":
        for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
            try:
                return list(pd.read_csv(path, nrows=3, encoding=enc).columns)
            except UnicodeDecodeError:
                continue
        return list(pd.read_csv(path, nrows=3, encoding_errors="replace").columns)
    if suffix in {".feather", ".ft"}:
        return list(pd.read_feather(path).columns)
    return []


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix == ".csv":
        last: Exception | None = None
        for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
            try:
                return pd.read_csv(path, encoding=enc, low_memory=False)
            except UnicodeDecodeError as exc:
                last = exc
        if last:
            raise last
    if suffix in {".feather", ".ft"}:
        return pd.read_feather(path)
    raise ValueError(f"Unsupported table: {path}")


def discover_panel(root: Path) -> tuple[pd.DataFrame, PanelDiscovery, list[PanelDiscovery]]:
    candidates: list[PanelDiscovery] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".parquet", ".pq", ".csv", ".feather", ".ft"}:
            continue
        try:
            columns = _peek_columns(path)
        except Exception:
            continue
        score = math.log10(max(path.stat().st_size, 10))
        if resolve_column(columns, ALIASES["receipt"]):
            score += 100
        if resolve_column(columns, ALIASES["proxy"]):
            score += 100
        if resolve_column(columns, ALIASES["issuer"]):
            score += 25
        if resolve_column(columns, ALIASES["date"]):
            score += 20
        if resolve_column(columns, ALIASES["product"]):
            score += 10
        if "panel" in path.name.lower():
            score += 10
        if "analysis" in path.name.lower():
            score += 5
        candidates.append(PanelDiscovery(path, score, columns, path.stat().st_size))
    if not candidates:
        raise FileNotFoundError("No CSV/Parquet/Feather files found in input ZIP")
    candidates.sort(key=lambda x: (x.score, x.size_bytes), reverse=True)
    viable = [c for c in candidates if resolve_column(c.columns, ALIASES["receipt"]) and resolve_column(c.columns, ALIASES["proxy"])]
    if not viable:
        top = [(str(c.path), c.columns[:20]) for c in candidates[:10]]
        raise RuntimeError(f"No table contains both receipt and proxy columns. Top candidates: {top}")
    chosen = viable[0]
    return read_table(chosen.path), chosen, candidates


def _numeric_or_nan(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    text = series.astype("string").str.replace(",", "", regex=False).str.replace("%", "", regex=False)
    out = pd.to_numeric(text, errors="coerce")
    # Percent-looking inputs larger than 1 are left in percentage-point units.
    return out


def _normalize_title_signature(series: pd.Series) -> pd.Series:
    s = series.astype("string").fillna("").str.lower()
    s = s.str.replace(r"\d{4}[-./]?\d{1,2}[-./]?\d{1,2}", "<date>", regex=True)
    s = s.str.replace(r"\b\d{6}\b", "<code>", regex=True)
    s = s.str.replace(r"\d+(?:\.\d+)?%?", "<num>", regex=True)
    s = s.str.replace(r"\s+", " ", regex=True).str.strip()
    return s


def normalize_panel(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = raw.copy()
    mapping: dict[str, str | None] = {k: resolve_column(df.columns, v) for k, v in ALIASES.items()}
    if not mapping["receipt"] or not mapping["proxy"]:
        raise RuntimeError("Required receipt/proxy columns not found after panel discovery")

    out = pd.DataFrame(index=df.index)
    out["receipt"] = coerce_binary(df[mapping["receipt"]], "receipt")
    out["proxy"] = coerce_binary(df[mapping["proxy"]], "proxy")

    out["issuer"] = (
        df[mapping["issuer"]].astype("string").fillna("UNKNOWN_ISSUER")
        if mapping["issuer"] else pd.Series("UNKNOWN_ISSUER", index=df.index, dtype="string")
    )
    out["product"] = (
        df[mapping["product"]].astype("string").fillna("UNKNOWN_PRODUCT")
        if mapping["product"] else pd.Series(np.arange(len(df)).astype(str), index=df.index, dtype="string")
    )
    if mapping["date"]:
        out["date"] = pd.to_datetime(df[mapping["date"]], errors="coerce")
    else:
        out["date"] = pd.NaT
    out["year"] = out["date"].dt.year.astype("Int64")
    out["month"] = out["date"].dt.to_period("M").astype("string")
    out["weekday"] = out["date"].dt.weekday.astype("Int64")

    out["receipt_id"] = (
        df[mapping["receipt_id"]].astype("string").replace({"nan": pd.NA, "None": pd.NA, "": pd.NA})
        if mapping["receipt_id"] else pd.Series(pd.NA, index=df.index, dtype="string")
    )
    out["filing_time"] = (
        pd.to_datetime(df[mapping["filing_time"]], errors="coerce")
        if mapping["filing_time"] else pd.NaT
    )
    out["title"] = (
        df[mapping["title"]].astype("string")
        if mapping["title"] else pd.Series(pd.NA, index=df.index, dtype="string")
    )
    out["title_signature"] = _normalize_title_signature(out["title"])
    out["title_length"] = out["title"].fillna("").str.len().astype(float)

    if mapping["batch_size"]:
        out["batch_size"] = _numeric_or_nan(df[mapping["batch_size"]]).fillna(1).clip(lower=1)
    elif out["receipt_id"].notna().any():
        counts = out.loc[out["receipt_id"].notna(), "receipt_id"].value_counts()
        out["batch_size"] = out["receipt_id"].map(counts).fillna(1).astype(float)
    elif out["date"].notna().any():
        out["batch_size"] = out.groupby(["issuer", "date"], dropna=False)["product"].transform("nunique").astype(float)
    else:
        out["batch_size"] = 1.0

    if mapping["batch"]:
        out["batch"] = coerce_binary(df[mapping["batch"]], "batch").fillna(0)
    else:
        out["batch"] = (out["batch_size"] > 1).astype("Int64")

    if mapping["multi_product"]:
        out["multi_product"] = coerce_binary(df[mapping["multi_product"]], "multi_product").fillna(0)
    else:
        out["multi_product"] = (out["batch_size"] > 1).astype("Int64")

    if mapping["correction"]:
        out["correction"] = coerce_binary(df[mapping["correction"]], "correction").fillna(0)
    else:
        out["correction"] = out["title"].fillna("").str.contains("정정|correction|amend", case=False, regex=True).astype("Int64")

    if mapping["severity"]:
        out["severity"] = _numeric_or_nan(df[mapping["severity"]]).abs()
    elif mapping["running"]:
        out["severity"] = _numeric_or_nan(df[mapping["running"]]).abs()
    else:
        out["severity"] = np.nan

    if mapping["running"]:
        out["running"] = _numeric_or_nan(df[mapping["running"]])
    else:
        out["running"] = np.nan

    if mapping["episode_length"]:
        out["episode_length"] = _numeric_or_nan(df[mapping["episode_length"]]).fillna(1).clip(lower=1)
    else:
        out["episode_length"] = 1.0

    if mapping["congestion"]:
        out["congestion"] = _numeric_or_nan(df[mapping["congestion"]])
    elif out["date"].notna().any():
        out["congestion"] = out.groupby("date", dropna=False)["product"].transform("nunique").astype(float)
    else:
        out["congestion"] = 1.0

    if mapping["candidate"]:
        out["candidate"] = coerce_binary(df[mapping["candidate"]], "candidate")
    else:
        out["candidate"] = pd.Series(pd.NA, index=df.index, dtype="Int64")

    if mapping["domestic"]:
        out["domestic"] = coerce_binary(df[mapping["domestic"]], "domestic")
    else:
        out["domestic"] = pd.Series(pd.NA, index=df.index, dtype="Int64")

    if mapping["staleness"]:
        out["staleness"] = _numeric_or_nan(df[mapping["staleness"]])
    else:
        out["staleness"] = np.nan

    for key in ["abs_ret_next1", "repeat_breach_1d", "repeat_breach_5d", "gap_reversion_1", "gap_reversion_5"]:
        if mapping[key]:
            out[key] = _numeric_or_nan(df[mapping[key]])

    out["miss"] = ((out["receipt"] == 1) & (out["proxy"] == 0)).astype("Int64")
    out["false_positive"] = ((out["receipt"] == 0) & (out["proxy"] == 1)).astype("Int64")
    out["exact_receipt_id"] = (out["receipt_id"].notna()).astype("Int64")
    out["issuer_date"] = out["issuer"].astype(str) + "|" + out["date"].astype(str)

    # Keep original columns with a prefix so advanced users can inspect without ambiguity.
    for col in df.columns:
        safe = re.sub(r"[^0-9A-Za-z가-힣_]+", "_", str(col)).strip("_")
        name = f"raw__{safe}"
        if name not in out.columns:
            out[name] = df[col]

    report = {
        "row_count": int(len(out)),
        "column_mapping": mapping,
        "normalized_columns": list(out.columns),
        "receipt_nonmissing": int(out["receipt"].notna().sum()),
        "proxy_nonmissing": int(out["proxy"].notna().sum()),
        "issuer_count": int(out["issuer"].nunique(dropna=True)),
        "product_count": int(out["product"].nunique(dropna=True)),
        "date_min": str(out["date"].min()),
        "date_max": str(out["date"].max()),
    }
    return out, report


def wilson_interval(successes: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    if total <= 0:
        return (float("nan"), float("nan"))
    from scipy.stats import norm
    z = norm.ppf(1 - alpha / 2)
    p = successes / total
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
    return max(0.0, center - half), min(1.0, center + half)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def ensure_dirs(root: Path, names: Iterable[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name in names:
        (root / name).mkdir(parents=True, exist_ok=True)


def clip_probability(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))
