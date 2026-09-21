#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(obj: object) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1", required=True)
    parser.add_argument("--v2", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--cost", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    v1 = json.loads(Path(args.v1).read_text(encoding="utf-8"))
    v2 = json.loads(Path(args.v2).read_text(encoding="utf-8"))
    protocol = json.loads(Path(args.protocol).read_text(encoding="utf-8"))
    cost = json.loads(Path(args.cost).read_text(encoding="utf-8"))

    protected_v1 = {
        "population_N": v1["workflow"]["target_units"],
        "threshold": 0.5,
        "risk_alpha": v1["risk"]["limit"],
        "loss_definition": {
            key: value
            for key, value in v1["loss_semantics"].items()
            if key != "strict_upper_bound"
        },
        "loss_bound_rule": v1["loss_semantics"]["strict_upper_bound"],
        "tree_semantics": v1["tree_semantics"],
        "canonical_truth_definition": v1["canonical_truth"],
        "cost_rule_digest": v1["cost_rule"]["cost_rule_digest"],
        "B7_portfolio": v1["strongest_b7"],
        "30X_gate": {
            "median": v1["hard_gates"]["median_speedup_vs_platform_b7"],
            "conservative": v1["hard_gates"]["conservative_speedup"],
            "class": v1["hard_gates"]["pretruth_theory_class"],
        },
        "audit_randomness_rule": v1["risk"]["freeze_c"],
    }
    protected_v2 = {key: v2[key] for key in protected_v1}
    rule_diffs = {
        key: {"v1": protected_v1[key], "v2": protected_v2[key]}
        for key in protected_v1
        if protected_v1[key] != protected_v2[key]
    }

    protocol_checks = {
        "explicit_protocol_version": protocol.get("schema") == "SAC_GEN7_QUALIFICATION_PROTOCOL_V2",
        "canonical_truth_role": protocol.get("canonical_truth_oracle", {}).get("role") == "scientific_adjudication_truth",
        "b7_role": protocol.get("b7_comparator", {}).get("role") == "strongest_deployable_full_audit_performance_denominator_only",
        "frozen_b7_membership": protocol.get("b7_comparator", {}).get("frozen_portfolio") == [
            "independent C++ 1-thread",
            "independent C++ 4-thread",
            "package-native vectorized scikit-learn",
        ],
        "package_native_raw_bits_diagnostic_only": "raw-bit identity is not a canonical-truth qualification" in protocol.get("b7_comparator", {}).get("qualification", {}).get("package_native_sklearn", []),
        "cost_digest_unchanged": cost["cost_rule_digest"] == protected_v1["cost_rule_digest"],
        "history_only": protocol.get("history_only") is True,
        "target_seeds_unused": protocol.get("target_seeds_used") is False,
        "freeze_a_v2_locked": protocol.get("freeze_a_v2_authorized_before_history_pass") is False,
    }

    delivery_only = [
        "remove Base64 source bundle",
        "remove chunk materializer",
        "publish direct source files",
        "replace workflow file paths",
        "cross-platform shell portability",
        "add compiler and numeric environment self-tests",
        "add single-use state machine",
        "add history-only dry run and resource preflight",
    ]
    protocol_diff = {
        "classification": "PRETARGET_QUALIFICATION_ROLE_SEPARATION",
        "before": "package-native B7 raw-bit identity was incorrectly included in canonical-truth qualification",
        "after": "strict C++ plus Decimal-40 defines truth; all qualified B7 modes remain denominator candidates",
        "target_result_used": False,
        "history_only_evidence": [42, 73],
        "prospective_target_identity_selected": False,
    }

    result = {
        "schema": "SAC_GEN7_PROTOCOL_AND_SCIENTIFIC_RULE_DIFF_V3",
        "v1_protected_digest": digest(protected_v1),
        "v2_protected_digest": digest(protected_v2),
        "scientific_rule_diffs": rule_diffs,
        "scientific_rule_diff_count": len(rule_diffs),
        "SCIENTIFIC_RULE_DIFF": len(rule_diffs),
        "qualification_protocol_diff": protocol_diff,
        "QUALIFICATION_PROTOCOL_DIFF": 1,
        "protocol_checks": protocol_checks,
        "delivery_only_diffs": delivery_only,
        "DELIVERY_ONLY_DIFF": len(delivery_only),
        "target_identity": {
            "v1_seeds": [2168, 912],
            "v1_seed_status": "CONSUMED_BY_PRIOR_LOCAL_REPORT_AND_FULL_TRUTH",
            "v2_seeds": "PENDING_DETERMINISTIC_SELECTION_AFTER_HISTORY_DRY_RUN",
            "classification": "MANDATORY_NEW_PROSPECTIVE_TARGET_IDENTITY_NOT_A_RULE_RETUNE",
            "pure_transport_supersession_possible": False,
        },
    }
    result["pass"] = not rule_diffs and all(protocol_checks.values())
    Path(args.out).write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "pass": result["pass"],
                "scientific_rule_diff": result["SCIENTIFIC_RULE_DIFF"],
                "qualification_protocol_diff": result["QUALIFICATION_PROTOCOL_DIFF"],
                "delivery_only_diff": result["DELIVERY_ONLY_DIFF"],
            },
            sort_keys=True,
        )
    )
    if not result["pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
