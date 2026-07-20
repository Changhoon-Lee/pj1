from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import run_topjournal_probe as base
from probe_utils import deterministic_zip, sha256_file


_original_normalize_panel = base.normalize_panel


def safe_normalize_panel(raw: pd.DataFrame):
    panel, report = _original_normalize_panel(raw)
    raw_columns = [c for c in panel.columns if c.startswith("raw__")]
    if raw_columns:
        panel = panel.drop(columns=raw_columns)
    report["raw_columns_dropped_from_normalized_output"] = raw_columns
    report["normalized_columns"] = list(panel.columns)
    return panel, report


def hardened_scorecard(
    confusion: dict[str, float],
    issuer_summary: dict[str, float],
    mechanism_summary: dict[str, float],
    fe_summary: dict[str, float],
    regression_summary: dict[str, float],
    calibration_summary: dict[str, float],
    robustness: pd.DataFrame,
    second_context_present: bool = False,
) -> tuple[pd.DataFrame, str]:
    relative_bias = abs(confusion.get("relative_prevalence_bias", np.nan))
    variance_bias = abs(issuer_summary.get("between_issuer_variance_bias", np.nan))
    economic_distortion = (
        issuer_summary.get("spearman_rho", 1.0) < 0.80
        or issuer_summary.get("quartile_reclassification_rate", 0.0) >= 0.25
        or (np.isfinite(variance_bias) and variance_bias >= 0.25)
        or regression_summary.get("max_absolute_relative_coefficient_bias", 0.0) >= 0.25
        or bool(regression_summary.get("any_sign_change", False))
    )
    mechanism_strength = max(
        mechanism_summary.get("architecture_logloss_improvement_vs_time", 0.0),
        mechanism_summary.get("architecture_increment_beyond_issuer", 0.0),
        fe_summary.get("issuer_fe_sd_attenuation_architecture", 0.0),
    )
    calibration_gain = calibration_summary.get("mae_improvement", np.nan)
    robust = True
    if robustness is not None and not robustness.empty:
        robust = (
            robustness["recall_change_from_full"].abs().max() <= 0.10
            and robustness["precision_change_from_full"].abs().max() <= 0.05
        )
    gate_data = [
        ("G1_material_prevalence_bias", np.isfinite(relative_bias) and relative_bias >= 0.25, relative_bias, ">=25% relative filing-prevalence bias"),
        ("G2_material_economic_conclusion_distortion", economic_distortion, float(economic_distortion), "sign change, coefficient/variance bias >=25%, rho<0.8, or quartile reclassification>=25%"),
        ("G3_document_architecture_mechanism", np.isfinite(mechanism_strength) and mechanism_strength >= 0.10, mechanism_strength, ">=10% predictive improvement or issuer-FE attenuation"),
        ("G4_out_of_sample_calibration", np.isfinite(calibration_gain) and calibration_gain >= 0.30, calibration_gain, ">=30% weighted held-out MAE improvement"),
        ("G5_leave_one_out_robustness", robust, float(robust), "recall shift<=10pp and precision shift<=5pp"),
        ("G6_independent_second_context", second_context_present, float(second_context_present), "independent open-data disclosure context"),
    ]
    scorecard = pd.DataFrame([
        {"gate": name, "pass": bool(passed), "value": value, "criterion": criterion}
        for name, passed, value, criterion in gate_data
    ])
    first_five = all(bool(x[1]) for x in gate_data[:5])
    if first_five and second_context_present:
        verdict = "GO_TOPJOURNAL_CANDIDATE_MEASUREMENT_ERROR"
    elif first_five:
        verdict = "GO_STRONG_MEASUREMENT_MECHANISM_PAPER_NEEDS_EXTERNAL_REPLICATION"
    elif bool(gate_data[0][1]):
        verdict = "GO_OPEN_DATA_MEASUREMENT_ERROR_PAPER"
    else:
        verdict = "STOP_NOT_MATERIALLY_IMPORTANT_WITH_CURRENT_DATA"
    return scorecard, verdict


def output_argument(argv: list[str]) -> Path | None:
    for i, token in enumerate(argv):
        if token == "--output" and i + 1 < len(argv):
            return Path(argv[i + 1]).resolve()
        if token.startswith("--output="):
            return Path(token.split("=", 1)[1]).resolve()
    return None


def rebuild_final_archive(out: Path) -> tuple[Path, str]:
    zip_path = out / "ETF_TOPJOURNAL_PROBE_RESULTS.zip"
    sha_path = out / "ETF_TOPJOURNAL_PROBE_RESULTS.zip.sha256"
    zip_path.unlink(missing_ok=True)
    sha_path.unlink(missing_ok=True)
    base.make_manifest(out, out / "audit" / "SOURCE_MANIFEST.sha256")
    deterministic_zip(out, zip_path)
    digest = sha256_file(zip_path)
    sha_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    return zip_path, digest


def main() -> int:
    base.normalize_panel = safe_normalize_panel
    base.build_scorecard = hardened_scorecard
    rc = base.main()
    out = output_argument(sys.argv[1:])
    if out is not None and out.exists():
        zip_path, digest = rebuild_final_archive(out)
        print(f"HARDENED_FINAL_ZIP={zip_path}")
        print(f"HARDENED_FINAL_SHA256={digest}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
