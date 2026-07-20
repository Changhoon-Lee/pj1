from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from probe_analysis import (
    architecture_stratification,
    bias_decomposition,
    build_scorecard,
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
from probe_utils import discover_panel, normalize_panel, safe_extract_zip


def synthetic_panel(seed: int = 1234, n: int = 8000) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    issuers = np.array([f"Issuer_{i:02d}" for i in range(12)])
    issuer = rng.choice(issuers, n)
    dates = pd.date_range("2021-01-01", periods=650, freq="D")
    date = rng.choice(dates, n)
    severity = np.abs(rng.normal(1.7, 0.8, n))
    congestion = rng.poisson(4, n) + 1
    batch_size = rng.choice([1, 1, 1, 2, 3, 5, 10], n)
    correction = rng.binomial(1, 0.08, n)
    issuer_effect = pd.Series(issuer).map({name: val for name, val in zip(issuers, np.linspace(-0.8, 0.8, len(issuers)))}).to_numpy()
    p_receipt = 1 / (1 + np.exp(-(-3.2 + 0.45 * severity - 0.05 * congestion + 0.15 * issuer_effect)))
    receipt = rng.binomial(1, p_receipt)
    capture_logit = 1.0 - 0.65 * np.log1p(batch_size) - 0.8 * correction + issuer_effect
    p_capture = 1 / (1 + np.exp(-capture_logit))
    captured = rng.binomial(1, p_capture)
    false_positive = rng.binomial(1, 0.0008, n)
    proxy = np.where(receipt == 1, captured, false_positive)
    receipt_id = np.where(receipt == 1, [f"R{v:08d}" for v in rng.integers(1, 2500, n)], None)
    repeat5 = rng.binomial(1, 1 / (1 + np.exp(-(-1 + 0.2 * severity))), n)
    absret = np.abs(rng.normal(0.012 + 0.002 * severity, 0.008, n))
    return pd.DataFrame({
        "issuer_name": issuer,
        "ticker": rng.choice([f"ETF{i:03d}" for i in range(97)], n),
        "event_date": date,
        "official_receipt": receipt,
        "proxy_filing": proxy,
        "acpt_no": receipt_id,
        "severity": severity,
        "congestion": congestion,
        "batch_size": batch_size,
        "is_correction": correction,
        "multi_product": (batch_size > 1).astype(int),
        "report_title": np.where(correction == 1, "정정 ETF 괴리율 초과 발생", "ETF 괴리율 초과 발생"),
        "candidate_event": rng.binomial(1, 0.15, n),
        "abs_ret_next1": absret,
        "repeat_breach_5d": repeat5,
    })


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "source"
        source.mkdir()
        raw = synthetic_panel()
        raw.to_parquet(source / "analysis_panel.parquet", index=False)
        zpath = root / "input.zip"
        with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(source / "analysis_panel.parquet", "analysis/analysis_panel.parquet")
        extracted = root / "extracted"
        safe_extract_zip(zpath, extracted)
        loaded, chosen, _ = discover_panel(extracted)
        assert chosen.path.name == "analysis_panel.parquet"
        panel, report = normalize_panel(loaded)
        assert len(panel) == len(raw)
        assert report["issuer_count"] == 12

        matrix, metrics, values = confusion_table_and_metrics(panel)
        assert values["precision_ppv"] > 0.95
        assert 0.1 < values["recall_sensitivity"] < 0.9
        assert matrix.shape == (2, 3)
        assert not denominator_audit(panel).empty

        issuer_table, eb, issuer_summary = issuer_metrics(panel)
        assert len(issuer_table) == 12
        assert not eb.empty
        rank_table, rank_summary = rank_distortion(issuer_table)
        assert len(rank_table) == 12
        dispersion = dispersion_distortion(issuer_table)
        assert len(dispersion) == 2

        mechanism_metrics, coefficients, mechanism_summary = mechanism_models(panel, 1234)
        assert len(mechanism_metrics) == 4
        assert mechanism_summary["status"] == "OK"
        assert not coefficients.empty

        fe_table, fe_summary = issuer_fe_attenuation(panel)
        assert fe_summary["status"] in {"OK", "FAILED"}
        assert not architecture_stratification(panel).empty

        regression_table, regression_summary = regression_distortion(panel)
        assert regression_summary["status"] in {"OK", "PARTIAL"}
        assert not regression_table.empty
        assert not market_association_distortion(panel).empty

        calibration, calibration_summary = cross_fitted_calibration(panel)
        assert calibration_summary["status"] == "OK"
        assert not calibration.empty

        monthly, break_summary = monthly_sensitivity_and_break(panel, 1234, permutations=19)
        assert not monthly.empty
        assert "status" in break_summary
        loo = leave_one_out_robustness(panel)
        assert not loo.empty
        assert not bias_decomposition(panel).empty

        issuer_summary.update(rank_summary)
        if "variance_bias_relative_to_receipt" in dispersion and dispersion["variance_bias_relative_to_receipt"].notna().any():
            issuer_summary["between_issuer_variance_bias"] = float(dispersion["variance_bias_relative_to_receipt"].dropna().iloc[0])
        scorecard, verdict = build_scorecard(
            values, issuer_summary, mechanism_summary, fe_summary,
            regression_summary, calibration_summary, loo, False,
        )
        assert len(scorecard) == 6
        assert verdict in {
            "GO_TOPJOURNAL_CANDIDATE_MEASUREMENT_ERROR",
            "GO_STRONG_MEASUREMENT_MECHANISM_PAPER_NEEDS_EXTERNAL_REPLICATION",
            "GO_OPEN_DATA_MEASUREMENT_ERROR_PAPER",
            "STOP_NOT_MATERIALLY_IMPORTANT_WITH_CURRENT_DATA",
        }

    print("SYNTHETIC_SMOKE_TEST_PASS")


if __name__ == "__main__":
    main()
