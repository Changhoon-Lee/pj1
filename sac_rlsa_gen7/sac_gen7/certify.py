from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .common import digest_obj, minimal_sample, sha256_file, write_json


def certify(report_path: Path, cost_path: Path, out: Path, alpha: float = 0.01) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    stored_digest = report.pop("canonical_report_digest")
    actual_digest = digest_obj(report)
    report["canonical_report_digest"] = stored_digest
    if stored_digest != actual_digest:
        raise RuntimeError("canonical report self-digest mismatch")
    cost = json.loads(cost_path.read_text(encoding="utf-8"))
    root = report_path.parent
    loss_path = root / report["files"]["loss"]["path"]
    if sha256_file(loss_path) != report["files"]["loss"]["sha256"]:
        raise RuntimeError("reported loss hash mismatch")
    loss = np.memmap(loss_path, dtype="<f8", mode="r", shape=(report["population"],))

    if not report["reported_decision"]:
        q_support, sample_size, miss, class_name = 0, report["population"], 1.0, "REPORTED_NEGATIVE_NO_CERTIFICATION"
    else:
        margin_total = (
            report["policy"]["threshold"] - report["reported_mean_loss"]
        ) * report["population"]
        caps = np.maximum(0.0, report["model_bounds"]["loss_upper"] - np.asarray(loss))
        ordered = np.sort(caps)[::-1]
        q_support = int(np.searchsorted(np.cumsum(ordered), margin_total, side="left") + 1)
        sample_size, miss = minimal_sample(report["population"], q_support, alpha)
        selected_upper = (
            cost["selected_fixed_upper_ns"]
            + cost["selected_per_action_upper_ns"] * sample_size
        )
        predicted = cost["full_b7_wall_lower_ns"] / selected_upper
        class_name = (
            "30X_CERTIFIED"
            if predicted >= 30
            else "10X_CERTIFIED"
            if predicted >= 10
            else "3X_CERTIFIED"
            if predicted >= 3
            else "UNRESOLVED"
        )

    selected_upper = (
        cost["selected_fixed_upper_ns"]
        + cost["selected_per_action_upper_ns"] * sample_size
    )
    certificate = {
        "schema": "SAC_GEN7_THEORY_CERTIFICATE_V1",
        "target_id": report["target_id"],
        "canonical_target_report_digest": stored_digest,
        "target_artifact_hashes": {
            key: value["sha256"] for key, value in sorted(report["files"].items())
        },
        "policy_digest": digest_obj(report["policy"]),
        "tree_semantics_digest": digest_obj(report["tree_semantics"]),
        "canonical_truth_digest": digest_obj(report["canonical_truth"]),
        "population": report["population"],
        "risk_limit": alpha,
        "reported_decision": report["reported_decision"],
        "reported_mean_loss": report["reported_mean_loss"],
        "threshold": report["policy"]["threshold"],
        "strict_loss_upper": report["model_bounds"]["loss_upper"],
        "strict_loss_bound_method": report["model_bounds"]["loss_bound"]["method"],
        "q_D_lower_bound": q_support,
        "sample_size": sample_size,
        "hypergeometric_miss_bound": miss,
        "cost_rule_digest": cost["cost_rule_digest"],
        "predicted_rlsa_wall_upper_ns": selected_upper,
        "predicted_b7_wall_lower_ns": cost["full_b7_wall_lower_ns"],
        "predicted_wall_speedup_lower": cost["full_b7_wall_lower_ns"] / selected_upper,
        "theory_class": class_name,
        "target_truth_accessed": False,
        "bad_state_family": "all truth vectors whose total adverse log-loss discrepancy can cross the frozen 0.5 decision threshold under the per-unit strict model-derived upper bound",
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
