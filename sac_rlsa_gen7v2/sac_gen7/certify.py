from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .common import digest_obj, minimal_sample, sha256_file, write_json


def selected_cost_upper(cost: dict, sample_size: int) -> float:
    if sample_size > int(cost.get("maximum_certifiable_sample_size", 8192)):
        return float("inf")
    return float(cost["selected_fixed_upper_ns"]) + float(cost["selected_per_action_upper_ns"]) * sample_size


def certify(report_path: Path, cost_path: Path, out: Path, alpha: float = 0.01) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    tmp = dict(report)
    stored_digest = tmp.pop("canonical_report_digest")
    if stored_digest != digest_obj(tmp):
        raise RuntimeError("canonical report self-digest mismatch")
    cost = json.loads(cost_path.read_text(encoding="utf-8"))
    root = report_path.parent
    loss_path = root / report["files"]["reported_loss"]["path"]
    if sha256_file(loss_path) != report["files"]["reported_loss"]["sha256"]:
        raise RuntimeError("reported loss hash mismatch")
    loss = np.memmap(loss_path, dtype="<f8", mode="r", shape=(report["population"],))

    tolerance = float(report["numeric_tolerance"]["risk_margin_reserve_per_unit"])
    effective_margin_per_unit = float(report["policy"]["threshold"]) - float(report["reported_mean_loss"]) - tolerance
    if not report["reported_decision"] or effective_margin_per_unit <= 0:
        q_support, sample_size, miss, class_name = 0, report["population"], 1.0, "REPORTED_NEGATIVE_OR_TOLERANCE_FRAGILE"
    else:
        margin_total = effective_margin_per_unit * report["population"]
        upper = float(report["model_bounds"]["loss_upper_binary64"])
        caps = np.maximum(0.0, upper - np.asarray(loss) - tolerance)
        ordered = np.sort(caps)[::-1]
        cumsum = np.cumsum(ordered, dtype=np.float64)
        q_support = int(np.searchsorted(cumsum, margin_total, side="left") + 1)
        sample_size, miss = minimal_sample(report["population"], q_support, alpha)
        selected_upper = selected_cost_upper(cost, sample_size)
        predicted = float(cost["full_b7_wall_lower_ns"]) / selected_upper
        class_name = (
            "30X_CERTIFIED" if predicted >= 30 else
            "10X_CERTIFIED" if predicted >= 10 else
            "3X_CERTIFIED" if predicted >= 3 else
            "UNRESOLVED"
        )

    selected_upper = selected_cost_upper(cost, sample_size)
    certificate = {
        "schema": "SAC_GEN7_THEORY_CERTIFICATE_V2",
        "target_id": report["target_id"],
        "target_report_digest": stored_digest,
        "target_report_file_sha256": sha256_file(report_path),
        "artifact_hashes": {key: value["sha256"] for key, value in sorted(report["files"].items())},
        "policy_digest": digest_obj(report["policy"]),
        "tree_semantics_digest": digest_obj(report["tree_semantics"]),
        "canonical_truth_spec_digest": digest_obj(report["canonical_truth"]),
        "numeric_tolerance_digest": digest_obj(report["numeric_tolerance"]),
        "population": report["population"],
        "risk_limit": alpha,
        "reported_decision": report["reported_decision"],
        "reported_mean_loss": report["reported_mean_loss"],
        "threshold": report["policy"]["threshold"],
        "risk_margin_reserve_per_unit": tolerance,
        "effective_margin_per_unit": effective_margin_per_unit,
        "strict_loss_upper": report["model_bounds"]["loss_upper_binary64"],
        "strict_loss_bound_method": report["model_bounds"]["loss_bound"]["construction"],
        "q_D_lower_bound": q_support,
        "sample_size": sample_size,
        "hypergeometric_miss_bound": miss,
        "cost_rule_digest": cost["cost_rule_digest"],
        "predicted_rlsa_wall_upper_ns": selected_upper,
        "predicted_b7_wall_lower_ns": cost["full_b7_wall_lower_ns"],
        "predicted_wall_speedup_lower": float(cost["full_b7_wall_lower_ns"]) / selected_upper,
        "theory_class": class_name,
        "target_truth_accessed": False,
        "bad_state_family": "all canonical-truth vectors whose total adverse excess over the frozen per-unit tolerance can cross the 0.5 decision threshold under the strict per-unit loss upper bound",
    }
    certificate["freeze_b_sha256"] = digest_obj(certificate)
    write_json(out, certificate)
    return certificate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--cost-rule", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    certificate = certify(Path(args.report), Path(args.cost_rule), Path(args.out))
    print(certificate["freeze_b_sha256"])


if __name__ == "__main__":
    main()
