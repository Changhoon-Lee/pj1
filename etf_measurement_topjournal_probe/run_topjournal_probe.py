from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from probe_analysis import (
    architecture_stratification,
    bias_decomposition,
    bootstrap_summary,
    build_scorecard,
    cluster_bootstrap_metrics,
    confusion_table_and_metrics,
    cross_fitted_calibration,
    denominator_audit,
    dispersion_distortion,
    issuer_fe_attenuation,
    issuer_metrics,
    leave_one_out_robustness,
    market_association_distortion,
    mechanism_models,
    monthly_sensitivity_and_break,
    rank_distortion,
    regression_distortion,
)
from probe_utils import (
    deterministic_zip,
    discover_panel,
    ensure_dirs,
    normalize_panel,
    safe_extract_zip,
    sha256_file,
    write_json,
)

EXPECTED_INPUT_SHA256 = "a56c4cb16d67b18c5723e8f207530e985aaade992067a36f755880db0a368d08"
SCRIPT_VERSION = "1.0.0"


class RunLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def log(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat()
        line = f"[{stamp}] {message}"
        print(line, flush=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


class StageRunner:
    def __init__(self, logger: RunLogger):
        self.logger = logger
        self.errors: list[dict[str, str]] = []

    def run(self, name: str, func: Callable[[], Any], fatal: bool = False) -> Any:
        self.logger.log(f"START {name}")
        try:
            result = func()
            self.logger.log(f"PASS  {name}")
            return result
        except Exception as exc:
            detail = traceback.format_exc()
            self.errors.append({"stage": name, "error": str(exc), "traceback": detail})
            self.logger.log(f"FAIL  {name}: {exc}")
            if fatal:
                raise
            return None


def save_table(df: pd.DataFrame | None, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if df is None:
        pd.DataFrame([{"status": "ANALYSIS_FAILED_OR_UNAVAILABLE"}]).to_csv(path, index=False, encoding="utf-8-sig")
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")


def _fmt_pct(x: float | None, digits: int = 2) -> str:
    if x is None or not np.isfinite(x):
        return "NA"
    return f"{100*x:.{digits}f}%"


def _fmt_num(x: float | None, digits: int = 4) -> str:
    if x is None or not np.isfinite(x):
        return "NA"
    return f"{x:.{digits}f}"


def detect_second_context(extracted: Path) -> tuple[bool, list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    for path in extracted.rglob("*"):
        if not path.is_file():
            continue
        low = path.name.lower()
        if "second_context" not in low and "table_13" not in low and "replication_context" not in low:
            continue
        record: dict[str, Any] = {"path": str(path.relative_to(extracted)), "size_bytes": path.stat().st_size}
        try:
            if path.suffix.lower() == ".csv":
                table = pd.read_csv(path)
                text = " ".join(table.astype(str).fillna("").to_numpy().ravel().tolist()).upper()
                record["rows"] = len(table)
            else:
                text = path.read_text(encoding="utf-8", errors="replace").upper()
            record["contains_no_eligible"] = "NO_ELIGIBLE_SECOND_CONTEXT" in text or "NO_ELIGIBLE" in text
            record["contains_go"] = "GO_" in text and not record["contains_no_eligible"]
        except Exception as exc:
            record["read_error"] = str(exc)
            record["contains_no_eligible"] = True
            record["contains_go"] = False
        evidence.append(record)
    present = any(r.get("contains_go", False) for r in evidence)
    return present, evidence


def plot_proxy_receipt_rates(issuer_table: pd.DataFrame, path: Path) -> None:
    x = issuer_table.dropna(subset=["proxy_rate", "receipt_rate"]).sort_values("receipt_rate")
    fig, ax = plt.subplots(figsize=(9, max(5, 0.23 * len(x))))
    y = np.arange(len(x))
    ax.scatter(x["proxy_rate"], y, marker="o", label="Proxy")
    ax.scatter(x["receipt_rate"], y, marker="x", label="Receipt")
    for i, row in enumerate(x.itertuples()):
        ax.plot([row.proxy_rate, row.receipt_rate], [i, i], linewidth=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(x["issuer"].astype(str), fontsize=7)
    ax.set_xlabel("Filing prevalence in common denominator")
    ax.set_title("Issuer filing rates: proxy versus official receipt")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_sensitivity_caterpillar(eb: pd.DataFrame, path: Path) -> None:
    x = eb.dropna(subset=["sensitivity_eb"]).sort_values("sensitivity_eb")
    fig, ax = plt.subplots(figsize=(9, max(5, 0.23 * len(x))))
    y = np.arange(len(x))
    lo = x["sensitivity_eb"] - x["sensitivity_eb_lo"]
    hi = x["sensitivity_eb_hi"] - x["sensitivity_eb"]
    ax.errorbar(x["sensitivity_eb"], y, xerr=np.vstack([lo, hi]), fmt="o", capsize=2)
    ax.set_yticks(y)
    ax.set_yticklabels(x["issuer"].astype(str), fontsize=7)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Empirical-Bayes sensitivity")
    ax.set_title("Issuer-dependent proxy detection of official receipts")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_mechanism_models(metrics: pd.DataFrame, path: Path) -> None:
    x = metrics.dropna(subset=["log_loss"]).copy()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x["model"], x["log_loss"])
    ax.set_ylabel("Out-of-fold log loss (lower is better)")
    ax.set_title("Does document architecture predict receipt omissions?")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_rank_change(rank: pd.DataFrame, path: Path) -> None:
    x = rank.dropna(subset=["proxy_rank", "receipt_rank"]).copy()
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(x["receipt_rank"], x["proxy_rank"])
    if not x.empty:
        lim = [0.5, max(x["receipt_rank"].max(), x["proxy_rank"].max()) + 0.5]
        ax.plot(lim, lim, linestyle="--")
        ax.set_xlim(lim)
        ax.set_ylim(lim)
    ax.set_xlabel("Receipt-based issuer rank")
    ax.set_ylabel("Proxy-based issuer rank")
    ax.set_title("Issuer rank distortion")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_calibration(table: pd.DataFrame, path: Path) -> None:
    x = table.dropna(subset=["receipt_rate_test", "proxy_rate_test", "corrected_rate_test"])
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(x["receipt_rate_test"], x["proxy_rate_test"], marker="o", label="Raw proxy")
    ax.scatter(x["receipt_rate_test"], x["corrected_rate_test"], marker="x", label="Cross-fitted correction")
    if not x.empty:
        mx = max(x[["receipt_rate_test", "proxy_rate_test", "corrected_rate_test"]].max().max(), 0.01)
        ax.plot([0, mx], [0, mx], linestyle="--")
        ax.set_xlim(0, mx)
        ax.set_ylim(0, mx)
    ax.set_xlabel("Official receipt prevalence in held-out group")
    ax.set_ylabel("Estimated prevalence")
    ax.set_title("Out-of-sample correction of proxy prevalence")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_monthly(monthly: pd.DataFrame, path: Path) -> None:
    x = monthly.dropna(subset=["sensitivity"]).copy()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x["month"].astype(str), x["sensitivity"], marker="o")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Proxy sensitivity among official receipts")
    ax.set_title("Time variation in proxy detection")
    ax.tick_params(axis="x", rotation=60)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_architecture(strata: pd.DataFrame, path: Path) -> None:
    x = strata[strata["dimension"].isin(["batch_size_bin", "correction", "multi_product"])].copy()
    x["label"] = x["dimension"] + ": " + x["stratum"]
    fig, ax = plt.subplots(figsize=(9, max(5, 0.35 * len(x))))
    y = np.arange(len(x))
    ax.errorbar(
        x["sensitivity"], y,
        xerr=np.vstack([x["sensitivity"] - x["wilson_lo"], x["wilson_hi"] - x["sensitivity"]]),
        fmt="o", capsize=2,
    )
    ax.set_yticks(y)
    ax.set_yticklabels(x["label"], fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Sensitivity")
    ax.set_title("Detection rates by document architecture")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_coefficients(regression: pd.DataFrame, path: Path) -> None:
    x = regression.dropna(subset=["receipt_coef", "proxy_coef"]).copy()
    fig, ax = plt.subplots(figsize=(8, max(4, 0.7 * len(x))))
    y = np.arange(len(x))
    ax.scatter(x["receipt_coef"], y, marker="x", label="Receipt outcome")
    ax.scatter(x["proxy_coef"], y, marker="o", label="Proxy outcome")
    for i, row in enumerate(x.itertuples()):
        ax.plot([row.receipt_coef, row.proxy_coef], [i, i], linewidth=0.8)
    ax.axvline(0, linewidth=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(x["term"])
    ax.set_xlabel("Two-way-FE coefficient")
    ax.set_title("Economic coefficient distortion")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def build_results_draft(
    path: Path,
    verdict: str,
    confusion: dict[str, float],
    issuer_summary: dict[str, float],
    mechanism_summary: dict[str, Any],
    fe_summary: dict[str, Any],
    regression_summary: dict[str, Any],
    calibration_summary: dict[str, Any],
    break_summary: dict[str, Any],
    second_context: bool,
) -> None:
    text = f"""# Results draft — generated from raw analysis panel

## Research question

Does the data-production architecture of public exchange filings create nonclassical
measurement error that changes economically relevant conclusions about disclosure?

## Core classification result

Using official receipt-level filings as the reference standard, the proxy has precision
**{_fmt_pct(confusion.get('precision_ppv'))}** and recall
**{_fmt_pct(confusion.get('recall_sensitivity'))}**. Product-day filing prevalence is
{_fmt_pct(confusion.get('receipt_prevalence'))} using official receipts and
{_fmt_pct(confusion.get('proxy_prevalence'))} using the proxy. The proxy-minus-receipt
bias is {_fmt_pct(confusion.get('absolute_prevalence_bias'))}, or
{_fmt_pct(confusion.get('relative_prevalence_bias'))} relative to receipt prevalence.
These are filing-prevalence statistics, not a legally adjudicated compliance rate.

## Issuer heterogeneity

The issuer heterogeneity test yields chi-square
{_fmt_num(issuer_summary.get('heterogeneity_chi2'), 2)} with p-value
{issuer_summary.get('heterogeneity_p', float('nan')):.3g}. The proxy and receipt issuer
rankings have Spearman rho {_fmt_num(issuer_summary.get('spearman_rho'), 3)} and the
quartile reclassification rate is
{_fmt_pct(issuer_summary.get('quartile_reclassification_rate'))}.

## Mechanism: document architecture versus issuer behavior

The architecture-only model changes out-of-fold log loss by
{_fmt_pct(mechanism_summary.get('architecture_logloss_improvement_vs_time'))} relative
to the time-only benchmark. Adding architecture and economic metadata beyond issuer
identity changes log loss by
{_fmt_pct(mechanism_summary.get('architecture_increment_beyond_issuer'))}. The standard
deviation of issuer fixed effects falls by
{_fmt_pct(fe_summary.get('issuer_fe_sd_attenuation_architecture'))} after document
architecture controls. This is the central diagnostic for whether measured issuer
heterogeneity partly reflects searchability and document design rather than behavior.

## Distortion of economic conclusions

The largest absolute relative difference between proxy-based and receipt-based
severity/congestion coefficients is
{_fmt_pct(regression_summary.get('max_absolute_relative_coefficient_bias'))}.
Coefficient sign change detected: {regression_summary.get('any_sign_change', False)}.
All such estimates are associational measurement-distortion comparisons, not causal
filing effects.

## Can the proxy be corrected out of sample?

A correction estimated without each held-out issuer/year changes weighted prevalence
MAE by {_fmt_pct(calibration_summary.get('mae_improvement'))}; the share of held-out
splits improved is {_fmt_pct(calibration_summary.get('share_splits_improved'))}.

## Exploratory time break

Status: {break_summary.get('status', 'NA')}. Candidate break:
{break_summary.get('break_after_month', 'NA')} to {break_summary.get('next_month', 'NA')};
max-stat permutation p-value {break_summary.get('max_stat_permutation_p', float('nan')):.3g}.
This break is data-selected and cannot be described as a policy effect.

## External replication

Independent second open-data disclosure context present: **{second_context}**.

## Machine verdict

**{verdict}**

The top-journal interpretation is allowed only when the scorecard separately passes
material economic distortion, document-architecture mechanism, out-of-sample correction,
leave-one-out robustness, and independent-context replication.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_final_verdict(
    path: Path,
    verdict: str,
    scorecard: pd.DataFrame,
    confusion: dict[str, float],
    errors: list[dict[str, str]],
    reproduced: bool,
) -> None:
    failed = scorecard.loc[~scorecard["pass"], "gate"].tolist() if not scorecard.empty else []
    text = f"""# FINAL VERDICT

## Verdict

`{verdict}`

## Raw-data reproduction gate

- Reported-result reproduction plausibility: **{reproduced}**
- Precision: {_fmt_pct(confusion.get('precision_ppv'))}
- Recall: {_fmt_pct(confusion.get('recall_sensitivity'))}
- False negatives: {int(confusion.get('FN', 0))}
- Relative filing-prevalence bias: {_fmt_pct(confusion.get('relative_prevalence_bias'))}

## Failed gates

{os.linesep.join('- ' + x for x in failed) if failed else '- None'}

## Nonfatal analysis errors

{os.linesep.join('- ' + e['stage'] + ': ' + e['error'] for e in errors) if errors else '- None'}

## Interpretation lock

This package tests whether public-filing **searchability and document architecture** create
nonclassical measurement error and whether that error changes empirical conclusions.
It does not identify the causal market effect of filing, issuer concealment, or legal
noncompliance.
"""
    path.write_text(text, encoding="utf-8")


def make_manifest(root: Path, manifest: Path) -> None:
    rows = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p != manifest and p.name != "ETF_TOPJOURNAL_PROBE_RESULTS.zip":
            rows.append(f"{sha256_file(p)}  {p.relative_to(root).as_posix()}")
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run targeted top-journal potential probes on Korean ETF disclosure measurement error.")
    parser.add_argument("--input", required=True, type=Path, help="KOREA_ETF_MEASUREMENT_ERROR_EMPIRICAL_RESULTS_FINAL.zip")
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument("--bootstrap", type=int, default=499)
    parser.add_argument("--permutations", type=int, default=999)
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--allow-sha-mismatch", action="store_true")
    args = parser.parse_args()

    input_zip = args.input.resolve()
    out = args.output.resolve()
    if out.exists():
        shutil.rmtree(out)
    ensure_dirs(out, ["audit", "data", "tables", "figures", "paper", "code", "_extracted"])
    logger = RunLogger(out / "audit" / "RUN_LOG.txt")
    stages = StageRunner(logger)

    logger.log(f"script_version={SCRIPT_VERSION}")
    logger.log(f"input={input_zip}")
    logger.log(f"output={out}")
    if not input_zip.exists():
        raise FileNotFoundError(input_zip)
    actual_sha = sha256_file(input_zip)
    (out / "audit" / "INPUT_SHA256.txt").write_text(
        f"expected  {EXPECTED_INPUT_SHA256}\nactual    {actual_sha}\n", encoding="utf-8"
    )
    if actual_sha != EXPECTED_INPUT_SHA256 and not args.allow_sha_mismatch:
        raise RuntimeError(
            f"Input SHA mismatch: expected {EXPECTED_INPUT_SHA256}, actual {actual_sha}. "
            "Use --allow-sha-mismatch only for an explicitly versioned new input."
        )

    stages.run("safe_extract", lambda: safe_extract_zip(input_zip, out / "_extracted"), fatal=True)
    second_context, second_context_evidence = detect_second_context(out / "_extracted")
    write_json(out / "audit" / "SECOND_CONTEXT_EVIDENCE.json", second_context_evidence)

    raw, chosen, candidates = stages.run(
        "discover_and_load_panel",
        lambda: discover_panel(out / "_extracted"),
        fatal=True,
    )
    discovery_table = pd.DataFrame([
        {
            "path": str(c.path.relative_to(out / "_extracted")),
            "score": c.score,
            "size_bytes": c.size_bytes,
            "columns": "|".join(c.columns),
            "chosen": c.path == chosen.path,
        }
        for c in candidates
    ])
    save_table(discovery_table, out / "audit" / "DATA_FILE_MAP.csv")
    logger.log(f"chosen_panel={chosen.path}; rows={len(raw)}; columns={len(raw.columns)}")

    panel, schema_report = stages.run("normalize_panel", lambda: normalize_panel(raw), fatal=True)
    write_json(out / "audit" / "SCHEMA_REPORT.json", schema_report)
    panel.to_parquet(out / "data" / "normalized_analysis_panel.parquet", index=False, compression="zstd")

    confusion_matrix, measurement_metrics, confusion_values = stages.run(
        "confusion_matrix", lambda: confusion_table_and_metrics(panel), fatal=True
    )
    counts = {
        "TP": int(confusion_matrix.loc[confusion_matrix["classification"] == "Proxy=1", "Receipt=1"].iloc[0]),
        "FP": int(confusion_matrix.loc[confusion_matrix["classification"] == "Proxy=1", "Receipt=0"].iloc[0]),
        "FN": int(confusion_matrix.loc[confusion_matrix["classification"] == "Proxy=0", "Receipt=1"].iloc[0]),
        "TN": int(confusion_matrix.loc[confusion_matrix["classification"] == "Proxy=0", "Receipt=0"].iloc[0]),
    }
    confusion_values.update(counts)
    reproduced = (
        abs(confusion_values["precision_ppv"] - 0.9853) <= 0.01
        and abs(confusion_values["recall_sensitivity"] - 0.4765) <= 0.03
        and 750 <= counts["FN"] <= 1000
    )
    if not reproduced:
        logger.log("WARNING: reported precision/recall/FN not reproduced within locked tolerances")

    save_table(confusion_matrix, out / "tables" / "table_15_confusion_matrix_recomputed.csv")
    save_table(measurement_metrics, out / "tables" / "table_16_measurement_metrics_recomputed.csv")

    denom = stages.run("denominator_audit", lambda: denominator_audit(panel))
    save_table(denom, out / "tables" / "table_17_denominator_audit.csv")

    issuer_boot = stages.run(
        "issuer_cluster_bootstrap",
        lambda: cluster_bootstrap_metrics(panel, ["issuer"], args.bootstrap, args.seed),
    )
    issuer_month_boot = stages.run(
        "issuer_month_block_bootstrap",
        lambda: cluster_bootstrap_metrics(panel.assign(issuer_month=panel["issuer"].astype(str) + "|" + panel["month"].astype(str)), ["issuer_month"], args.bootstrap, args.seed + 1),
    )
    boot_summary = pd.concat([
        bootstrap_summary(issuer_boot, "issuer"),
        bootstrap_summary(issuer_month_boot, "issuer_month"),
    ], ignore_index=True)
    save_table(boot_summary, out / "tables" / "table_18_cluster_bootstrap.csv")

    issuer_result = stages.run("issuer_metrics", lambda: issuer_metrics(panel))
    issuer_table, issuer_eb, issuer_summary = issuer_result if issuer_result else (pd.DataFrame(), pd.DataFrame(), {})
    save_table(issuer_table, out / "tables" / "table_19_issuer_metrics.csv")
    save_table(issuer_eb, out / "tables" / "table_20_issuer_empirical_bayes.csv")
    write_json(out / "tables" / "table_20_issuer_summary.json", issuer_summary)

    mechanism_result = stages.run("mechanism_models", lambda: mechanism_models(panel, args.seed))
    mechanism_metrics, mechanism_coefficients, mechanism_summary = mechanism_result if mechanism_result else (pd.DataFrame(), pd.DataFrame(), {})
    save_table(mechanism_metrics, out / "tables" / "table_21_mechanism_oof_models.csv")
    save_table(mechanism_coefficients, out / "tables" / "table_22_mechanism_coefficients.csv")
    write_json(out / "tables" / "table_21_mechanism_summary.json", mechanism_summary)

    fe_result = stages.run("issuer_fe_attenuation", lambda: issuer_fe_attenuation(panel))
    fe_table, fe_summary = fe_result if fe_result else (pd.DataFrame(), {})
    save_table(fe_table, out / "tables" / "table_23_issuer_fe_attenuation.csv")
    write_json(out / "tables" / "table_23_issuer_fe_attenuation_summary.json", fe_summary)

    strata = stages.run("architecture_stratification", lambda: architecture_stratification(panel))
    save_table(strata, out / "tables" / "table_24_architecture_stratification.csv")

    rank_result = stages.run("rank_distortion", lambda: rank_distortion(issuer_table))
    rank_table, rank_summary = rank_result if rank_result else (pd.DataFrame(), {})
    save_table(rank_table, out / "tables" / "table_25_rank_distortion.csv")
    write_json(out / "tables" / "table_25_rank_summary.json", rank_summary)
    issuer_summary.update(rank_summary)

    dispersion = stages.run("dispersion_distortion", lambda: dispersion_distortion(issuer_table))
    save_table(dispersion, out / "tables" / "table_26_dispersion_distortion.csv")
    if dispersion is not None and len(dispersion) == 2 and "variance_bias_relative_to_receipt" in dispersion:
        issuer_summary["between_issuer_variance_bias"] = float(dispersion["variance_bias_relative_to_receipt"].dropna().iloc[0]) if dispersion["variance_bias_relative_to_receipt"].notna().any() else np.nan

    regression_result = stages.run("regression_distortion", lambda: regression_distortion(panel))
    regression_table, regression_summary = regression_result if regression_result else (pd.DataFrame(), {})
    save_table(regression_table, out / "tables" / "table_27_regression_distortion.csv")
    write_json(out / "tables" / "table_27_regression_summary.json", regression_summary)

    market_assoc = stages.run("market_association_distortion", lambda: market_association_distortion(panel))
    save_table(market_assoc, out / "tables" / "table_28_market_association_distortion.csv")

    calibration_result = stages.run("cross_fitted_calibration", lambda: cross_fitted_calibration(panel))
    calibration_table, calibration_summary = calibration_result if calibration_result else (pd.DataFrame(), {})
    save_table(calibration_table, out / "tables" / "table_29_cross_fitted_calibration.csv")
    write_json(out / "tables" / "table_29_calibration_summary.json", calibration_summary)

    monthly_result = stages.run(
        "monthly_sensitivity_break",
        lambda: monthly_sensitivity_and_break(panel, args.seed, args.permutations),
    )
    monthly_table, break_summary = monthly_result if monthly_result else (pd.DataFrame(), {})
    save_table(monthly_table, out / "tables" / "table_30_monthly_sensitivity.csv")
    write_json(out / "tables" / "table_30_exploratory_break.json", break_summary)

    robustness = stages.run("leave_one_out_robustness", lambda: leave_one_out_robustness(panel))
    save_table(robustness, out / "tables" / "table_31_leave_one_out.csv")

    decomposition = stages.run("bias_decomposition", lambda: bias_decomposition(panel))
    save_table(decomposition, out / "tables" / "table_32_bias_decomposition.csv")

    scorecard, verdict = build_scorecard(
        confusion_values,
        issuer_summary,
        mechanism_summary,
        fe_summary,
        regression_summary,
        calibration_summary,
        robustness if robustness is not None else pd.DataFrame(),
        second_context_present=second_context,
    )
    if not reproduced:
        verdict = "STOP_REPORTED_RESULTS_NOT_REPRODUCED"
    save_table(scorecard, out / "TOPJOURNAL_SCORECARD.csv")

    # Figures are nonfatal; every plot uses one independent figure.
    stages.run("figure_proxy_receipt", lambda: plot_proxy_receipt_rates(issuer_table, out / "figures" / "figure_01_proxy_vs_receipt_rate.png"))
    stages.run("figure_sensitivity", lambda: plot_sensitivity_caterpillar(issuer_eb, out / "figures" / "figure_02_issuer_sensitivity_caterpillar.png"))
    stages.run("figure_mechanism", lambda: plot_mechanism_models(mechanism_metrics, out / "figures" / "figure_03_mechanism_logloss.png"))
    stages.run("figure_rank", lambda: plot_rank_change(rank_table, out / "figures" / "figure_04_issuer_rank_change.png"))
    stages.run("figure_calibration", lambda: plot_calibration(calibration_table, out / "figures" / "figure_05_calibration_scatter.png"))
    stages.run("figure_monthly", lambda: plot_monthly(monthly_table, out / "figures" / "figure_06_monthly_sensitivity.png"))
    stages.run("figure_architecture", lambda: plot_architecture(strata, out / "figures" / "figure_07_architecture_sensitivity.png"))
    stages.run("figure_coefficients", lambda: plot_coefficients(regression_table, out / "figures" / "figure_08_coefficient_distortion.png"))

    build_results_draft(
        out / "paper" / "RESULTS_DRAFT.md",
        verdict,
        confusion_values,
        issuer_summary,
        mechanism_summary,
        fe_summary,
        regression_summary,
        calibration_summary,
        break_summary,
        second_context,
    )
    (out / "paper" / "RESEARCH_PITCH.md").write_text(
        "# Research pitch\n\n"
        "Public filing data contain a separate, endogenous observability layer: document batching, "
        "templates, corrections, identifiers, and issuer-specific filing architecture determine whether "
        "an economically identical official filing is captured by a convenient research proxy. The paper "
        "measures that layer against official receipt IDs, tests whether it explains apparent issuer "
        "heterogeneity, quantifies how it changes empirical conclusions, and evaluates whether transparent "
        "cross-fitted calibration repairs the bias in held-out issuers and years.\n",
        encoding="utf-8",
    )
    (out / "paper" / "ALLOWED_CLAIMS.md").write_text(
        "# Allowed claims\n\n"
        "- Official receipt and proxy classification differ materially when reproduced from the common panel.\n"
        "- Missingness is nonclassical only to the extent supported by issuer/document-architecture tests.\n"
        "- Proxy-versus-receipt regression differences are measurement-distortion comparisons, not causal effects.\n"
        "- Product-day and candidate-event rates must be named by their actual denominator.\n",
        encoding="utf-8",
    )
    (out / "paper" / "FORBIDDEN_CLAIMS.md").write_text(
        "# Forbidden claims\n\n"
        "- Issuers concealed filings.\n"
        "- The proxy caused market outcomes.\n"
        "- Receipt search proves the legal compliance denominator.\n"
        "- A data-selected time break is a policy shock.\n"
        "- All KIND research is invalid.\n"
        "- Top-journal readiness without an independent second context.\n",
        encoding="utf-8",
    )

    build_final_verdict(out / "FINAL_VERDICT.md", verdict, scorecard, confusion_values, stages.errors, reproduced)
    write_json(out / "audit" / "NONFATAL_ERRORS.json", stages.errors)
    write_json(out / "audit" / "RUN_SUMMARY.json", {
        "script_version": SCRIPT_VERSION,
        "input_sha256": actual_sha,
        "chosen_panel": str(chosen.path.relative_to(out / "_extracted")),
        "normalized_rows": len(panel),
        "precision": confusion_values.get("precision_ppv"),
        "recall": confusion_values.get("recall_sensitivity"),
        "FN": counts["FN"],
        "relative_prevalence_bias": confusion_values.get("relative_prevalence_bias"),
        "verdict": verdict,
        "second_context": second_context,
        "nonfatal_error_count": len(stages.errors),
    })
    (out / "audit" / "SESSION_INFO.txt").write_text(
        f"python={sys.version}\nplatform={platform.platform()}\nscript_version={SCRIPT_VERSION}\n",
        encoding="utf-8",
    )

    # Copy the exact executable source into the result package.
    source_dir = Path(__file__).resolve().parent
    for name in ["run_topjournal_probe.py", "probe_analysis.py", "probe_utils.py", "requirements.txt", "README_ZCODE_KO.md"]:
        src = source_dir / name
        if src.exists():
            shutil.copy2(src, out / "code" / name)

    # Remove extracted upstream package from final result to avoid nested bulk duplication.
    shutil.rmtree(out / "_extracted", ignore_errors=True)
    manifest = out / "audit" / "SOURCE_MANIFEST.sha256"
    make_manifest(out, manifest)
    zip_path = out / "ETF_TOPJOURNAL_PROBE_RESULTS.zip"
    deterministic_zip(out, zip_path)
    final_sha = sha256_file(zip_path)
    (out / "ETF_TOPJOURNAL_PROBE_RESULTS.zip.sha256").write_text(
        f"{final_sha}  {zip_path.name}\n", encoding="utf-8"
    )

    logger.log(f"FINAL verdict={verdict}")
    logger.log(f"FINAL zip={zip_path}")
    logger.log(f"FINAL sha256={final_sha}")
    print(json.dumps({
        "zip": str(zip_path),
        "sha256": final_sha,
        "verdict": verdict,
        "precision": confusion_values.get("precision_ppv"),
        "recall": confusion_values.get("recall_sensitivity"),
        "false_negatives": counts["FN"],
        "failed_gates": scorecard.loc[~scorecard["pass"], "gate"].tolist(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
