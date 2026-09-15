#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sac_gen7.common import digest_obj, write_json
from sac_gen7.state_machine import transition, verify


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--state3", required=True); p.add_argument("--ubuntu", required=True); p.add_argument("--macos", required=True)
    p.add_argument("--out-state4", required=True); p.add_argument("--out-state5", required=True); p.add_argument("--out-state6", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    state3 = json.loads(Path(args.state3).read_text(encoding="utf-8")); verify(state3)
    ubuntu = json.loads(Path(args.ubuntu).read_text(encoding="utf-8")); macos = json.loads(Path(args.macos).read_text(encoding="utf-8"))
    if state3["state"] != 3 or not ubuntu["pass"] or not macos["pass"]:
        raise RuntimeError("full-platform prerequisite failure")
    ur = {int(r["seed"]): r for r in ubuntu["records"]}; mr = {int(r["seed"]): r for r in macos["records"]}
    if set(ur) != set(mr): raise RuntimeError("full target set mismatch")
    checks = []
    for seed in sorted(ur):
        a, b = ur[seed], mr[seed]
        item = {
            "seed": seed,
            "same_report_digest": a["report_digest"] == b["report_digest"],
            "same_target_bytes_digest": a["target_bytes_digest"] == b["target_bytes_digest"],
            "same_strict_raw_sha256": a["strict_raw_truth_sha256"] == b["strict_raw_truth_sha256"],
            "same_canonical_decimal_loss_sha256": a["canonical_truth"]["canonical_loss_lines_sha256"] == b["canonical_truth"]["canonical_loss_lines_sha256"],
            "same_canonical_mean": a["canonical_truth"]["canonical_mean_string"] == b["canonical_truth"]["canonical_mean_string"],
            "same_decision": a["full_truth_decision"] == b["full_truth_decision"],
            "zero_mismatch_both": a["unit_truth_zero_mismatch"] and b["unit_truth_zero_mismatch"],
            "complete_b7_both": a["complete_b7_executed"] and b["complete_b7_executed"],
            "median_30x_both": a["measured_wall_speedup"] >= 30 and b["measured_wall_speedup"] >= 30,
            "conservative_10x_both": a["conservative_p05_over_p95_wall_speedup"] >= 10 and b["conservative_p05_over_p95_wall_speedup"] >= 10,
        }
        item["pass"] = all(value for key, value in item.items() if key != "seed")
        checks.append(item)
    passed = all(item["pass"] for item in checks)
    summary = {
        "schema": "SAC_GEN7_CROSS_PLATFORM_FINAL_SUMMARY_V2",
        "ubuntu_receipt_digest": ubuntu["receipt_digest"], "macos_receipt_digest": macos["receipt_digest"],
        "checks": checks, "pass": passed,
    }
    summary["digest"] = digest_obj(summary)
    write_json(Path(args.out), summary)
    state4 = transition(state3, 4, "BOTH_PLATFORM_FULL_TRUTH_COMPLETE")
    write_json(Path(args.out_state4), state4)
    state5 = transition(state4, 5, "CANONICAL_CROSS_PLATFORM_AND_COMPLETE_B7_ADJUDICATED")
    write_json(Path(args.out_state5), state5)
    state6 = transition(state5, 6, "FINAL_HARD_GATES_ADJUDICATED_PASS" if passed else "FINAL_HARD_GATES_ADJUDICATED_FAIL")
    write_json(Path(args.out_state6), state6)
    if not passed: raise RuntimeError(f"cross-platform final gate failed: {checks}")


if __name__ == "__main__":
    main()
