#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sac_gen7.common import write_json
from sac_gen7.state_machine import transition, verify


def package_native_diagnostics(record: dict) -> dict:
    return record.get("diagnostic", {}).get("package_native", {})


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ubuntu", required=True)
    p.add_argument("--macos", required=True)
    p.add_argument("--build-manifest", required=True)
    p.add_argument("--state2", required=True)
    p.add_argument("--state-out-dir", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    ubuntu = json.loads(Path(args.ubuntu).read_text(encoding="utf-8"))
    macos = json.loads(Path(args.macos).read_text(encoding="utf-8"))
    build = json.loads(Path(args.build_manifest).read_text(encoding="utf-8"))
    state2 = json.loads(Path(args.state2).read_text(encoding="utf-8"))
    verify(state2)
    if state2["state"] != 2:
        raise RuntimeError("history aggregate requires STATE_2")

    ur = {int(record["seed"]): record for record in ubuntu["records"]}
    mr = {int(record["seed"]): record for record in macos["records"]}
    if set(ur) != set(mr):
        raise RuntimeError("history seed set mismatch")

    comparisons = []
    for seed in sorted(ur):
        a, b = ur[seed], mr[seed]
        checks = {
            "same_report_digest": a["report_digest"] == b["report_digest"],
            "same_target_bytes_digest": a["target_bytes_digest"] == b["target_bytes_digest"],
            "same_strict_raw_sha256": a["strict_raw_truth_sha256"] == b["strict_raw_truth_sha256"],
            "same_canonical_decimal_loss_sha256": a["canonical_truth"]["canonical_loss_lines_sha256"] == b["canonical_truth"]["canonical_loss_lines_sha256"],
            "same_canonical_mean": a["canonical_truth"]["canonical_mean_string"] == b["canonical_truth"]["canonical_mean_string"],
            "same_decision": a["canonical_truth"]["decision"] == b["canonical_truth"]["decision"],
            "selected_before_full": a["selected_before_full"] and b["selected_before_full"],
            "canonical_oracle_qualified_both": a["canonical_oracle_qualification"]["pass"] and b["canonical_oracle_qualification"]["pass"],
            "complete_b7_both": a["complete_b7_executed"] and b["complete_b7_executed"],
            "b7_portfolio_qualified_both": a["b7_portfolio_qualification"]["pass"] and b["b7_portfolio_qualification"]["pass"],
            "platform_pass_both": a["pass"] and b["pass"],
        }
        comparisons.append(
            {
                "seed": seed,
                "checks": checks,
                "pass": all(checks.values()),
                "diagnostics": {
                    "ubuntu_package_native": package_native_diagnostics(a),
                    "macos_package_native": package_native_diagnostics(b),
                    "package_native_raw_bit_identity_is_not_canonical_truth_gate": True,
                },
            }
        )

    resource = {
        "artifact_bytes": build["artifact_bytes"],
        "artifact_under_disk_budget": build["artifact_bytes"] <= 3_000_000_000,
        "artifact_under_upload_budget": build["artifact_bytes"] <= 1_500_000_000,
        "ubuntu_peak_rss_native_units": ubuntu["peak_rss_native_units"],
        "macos_peak_rss_native_units": macos["peak_rss_native_units"],
        "decimal_runtime_ubuntu_ns": sum(r["canonical_truth"]["wall_ns"] for r in ubuntu["records"]),
        "decimal_runtime_macos_ns": sum(r["canonical_truth"]["wall_ns"] for r in macos["records"]),
        "complete_b7_runtime_ubuntu_ns": sum(sum(mode["external_wall_median_ns"] for mode in r["complete_b7"].values()) for r in ubuntu["records"]),
        "complete_b7_runtime_macos_ns": sum(sum(mode["external_wall_median_ns"] for mode in r["complete_b7"].values()) for r in macos["records"]),
        "job_timeout_minutes": 180,
        "artifact_retention_days": 14,
    }

    passed = (
        ubuntu["pass"]
        and macos["pass"]
        and all(c["pass"] for c in comparisons)
        and resource["artifact_under_disk_budget"]
        and resource["artifact_under_upload_budget"]
    )
    result = {
        "schema": "SAC_GEN7_HISTORY_DRY_RUN_AGGREGATE_V3",
        "protocol": "CANONICAL_ORACLE_AND_B7_COMPARATOR_SEPARATED",
        "build_manifest_digest": build["manifest_digest"],
        "ubuntu_pass": ubuntu["pass"],
        "macos_pass": macos["pass"],
        "comparisons": comparisons,
        "resource_preflight": resource,
        "target_seeds_used": False,
        "pass": passed,
    }

    state_dir = Path(args.state_out_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    if passed:
        state3 = transition(state2, 3, "HISTORY_SELECTED_AUDITS_COMPLETE")
        write_json(state_dir / "HISTORY_STATE_3.json", state3)
        state4 = transition(state3, 4, "HISTORY_FULL_TRUTH_COMPLETE")
        write_json(state_dir / "HISTORY_STATE_4.json", state4)
        state5 = transition(state4, 5, "HISTORY_TWO_PLATFORM_COMPARISON_COMPLETE")
        write_json(state_dir / "HISTORY_STATE_5.json", state5)
        state6 = transition(state5, 6, "HISTORY_DRY_RUN_FINAL_ADJUDICATION_PASS")
        write_json(state_dir / "HISTORY_STATE_6.json", state6)
        result["state_machine_final_digest"] = state6["state_digest"]
    else:
        failure = {
            "schema": "SAC_GEN7_HISTORY_DRY_RUN_FAILURE_STATE_V1",
            "last_valid_state": state2,
            "reason": "HISTORY_TWO_PLATFORM_QUALIFICATION_FAILED",
            "target_seeds_used": False,
        }
        write_json(state_dir / "HISTORY_STATE_FAILURE.json", failure)
        result["state_machine_final_digest"] = None

    Path(args.out).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": result["pass"], "comparisons": comparisons}, sort_keys=True))
    if not result["pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
