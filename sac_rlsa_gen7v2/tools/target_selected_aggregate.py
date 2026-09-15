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
    p.add_argument("--state2", required=True); p.add_argument("--ubuntu", required=True); p.add_argument("--macos", required=True)
    p.add_argument("--out-state3", required=True); p.add_argument("--out", required=True)
    args = p.parse_args()
    state2 = json.loads(Path(args.state2).read_text(encoding="utf-8")); verify(state2)
    ubuntu = json.loads(Path(args.ubuntu).read_text(encoding="utf-8")); macos = json.loads(Path(args.macos).read_text(encoding="utf-8"))
    if state2["state"] != 2 or not ubuntu["pass"] or not macos["pass"]:
        raise RuntimeError("selected-audit platform gate failure")
    ur = {int(r["seed"]): r for r in ubuntu["records"]}; mr = {int(r["seed"]): r for r in macos["records"]}
    if set(ur) != set(mr): raise RuntimeError("selected target set mismatch")
    checks = []
    for seed in sorted(ur):
        a, b = ur[seed], mr[seed]
        item = {
            "seed": seed,
            "same_report": a["report_digest"] == b["report_digest"],
            "same_freeze_b": a["freeze_b_sha256"] == b["freeze_b_sha256"],
            "same_freeze_c": a["freeze_c_sha256"] == b["freeze_c_sha256"],
            "same_indices": a["indices_sha256"] == b["indices_sha256"],
            "both_clean": a["selected_clean"] and b["selected_clean"],
        }
        item["pass"] = all(value for key, value in item.items() if key != "seed")
        checks.append(item)
    summary = {
        "schema": "SAC_GEN7_SELECTED_CROSS_PLATFORM_AGGREGATE_V2",
        "ubuntu_receipt_digest": ubuntu["receipt_digest"], "macos_receipt_digest": macos["receipt_digest"],
        "checks": checks, "full_truth_accessed": False,
        "pass": all(item["pass"] for item in checks),
    }
    if not summary["pass"]: raise RuntimeError(f"selected cross-platform disagreement: {checks}")
    summary["digest"] = digest_obj(summary)
    write_json(Path(args.out), summary)
    state3 = transition(state2, 3, "BOTH_PLATFORM_SELECTED_AUDITS_COMPLETE_AND_PUBLIC")
    write_json(Path(args.out_state3), state3)


if __name__ == "__main__":
    main()
