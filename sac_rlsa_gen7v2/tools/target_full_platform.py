#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sac_gen7.state_machine import verify
from history_platform_run import canonical_truth, sha, timed_cpp, timed_sklearn


def digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--freeze-a", required=True); p.add_argument("--state3", required=True)
    p.add_argument("--selected", required=True); p.add_argument("--selected-aggregate", required=True)
    p.add_argument("--artifact-root", required=True); p.add_argument("--freeze-root", required=True)
    p.add_argument("--oracle", required=True); p.add_argument("--out", required=True)
    p.add_argument("--warmups", type=int, default=2); p.add_argument("--runs", type=int, default=11)
    args = p.parse_args()
    freeze_a = json.loads(Path(args.freeze_a).read_text(encoding="utf-8"))
    state3 = json.loads(Path(args.state3).read_text(encoding="utf-8")); verify(state3)
    selected = json.loads(Path(args.selected).read_text(encoding="utf-8"))
    selected_aggregate = json.loads(Path(args.selected_aggregate).read_text(encoding="utf-8"))
    if state3["state"] != 3 or state3["target_truth_accessed"] or not selected["pass"] or not selected_aggregate["pass"]:
        raise RuntimeError("full truth requires public STATE_3 and clean selected receipts")
    artifact_root = Path(args.artifact_root); oracle = Path(args.oracle).resolve(); selected_map = {int(r["seed"]): r for r in selected["records"]}
    records = []
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        for target in freeze_a["untouched_targets"]:
            seed = int(target["seed"]); target_id = target["target_id"]
            target_dir = artifact_root / f"seed{seed}"; report_path = target_dir / f"{target_id}.SCIENTIFIC_TARGET_REPORT.json"
            report = json.loads(report_path.read_text(encoding="utf-8")); selected_record = selected_map[seed]
            cpp1 = timed_cpp(oracle, target_dir, report, None, 1, args.warmups, args.runs, work, f"{seed}.cpp1", True)
            cpp4 = timed_cpp(oracle, target_dir, report, None, 4, args.warmups, args.runs, work, f"{seed}.cpp4", True)
            sklearn = timed_sklearn(target_dir, report_path, report, args.warmups, args.runs, work, f"{seed}.sklearn")
            modes = {"strict_cpp_1thread": cpp1, "strict_cpp_4thread": cpp4, "vectorized_sklearn": sklearn}
            strongest_name = min(modes, key=lambda name: modes[name]["external_wall_median_ns"]); strongest = modes[strongest_name]
            canonical = canonical_truth(
                Path(cpp1["truth_raw_path"]), target_dir / report["files"]["y"]["path"], report["population"],
                target_dir / report["files"]["reported_loss"]["path"], work / f"{seed}.canonical.json", None,
                report["numeric_tolerance"]["canonical_decimal_vs_reported_loss_abs"],
            )
            raw_exact = cpp1["truth_raw_sha256"] == cpp4["truth_raw_sha256"] == sklearn["truth_raw_sha256"] == report["files"]["reported_raw"]["sha256"] and all(mode["raw_mismatches_max"] == 0 for mode in modes.values())
            loss_sound = all(mode["loss_interval_mismatches_max"] == 0 and mode["loss_bound_violations_max"] == 0 for mode in modes.values()) and canonical["reported_loss_mismatches"] == 0
            speed = strongest["external_wall_median_ns"] / selected_record["selected_median_ns"]
            conservative = min(mode["external_wall_p05_ns"] for mode in modes.values()) / selected_record["selected_p95_ns"]
            record = {
                "seed": seed, "target_id": target_id,
                "report_digest": report["canonical_report_digest"],
                "selected_receipt_digest": selected_record["receipt_digest"], "selected_before_full": True,
                "complete_b7": modes, "complete_b7_executed": set(modes) == {"strict_cpp_1thread", "strict_cpp_4thread", "vectorized_sklearn"},
                "strongest_b7_mode": strongest_name, "strict_raw_truth_sha256": cpp1["truth_raw_sha256"],
                "canonical_truth": canonical, "raw_exact_agreement": raw_exact, "loss_sound_agreement": loss_sound,
                "full_truth_decision": canonical["decision"], "reported_decision": report["reported_decision"],
                "measured_wall_speedup": speed, "conservative_p05_over_p95_wall_speedup": conservative,
                "unit_truth_zero_mismatch": raw_exact and loss_sound,
                "target_bytes_digest": hashlib.sha256("".join(v["sha256"] for _, v in sorted(report["files"].items())).encode("ascii")).hexdigest(),
            }
            record["pass"] = raw_exact and loss_sound and canonical["decision"] == report["reported_decision"] and speed >= 30 and conservative >= 10
            record["receipt_digest"] = digest(record)
            records.append(record)
    output = {
        "schema": "SAC_GEN7_FULL_PLATFORM_RECEIPT_V2", "platform": platform.platform(), "machine": platform.machine(),
        "python": sys.version.split()[0], "oracle_sha256": sha(oracle), "records": records,
        "pass": all(record["pass"] for record in records),
    }
    output["receipt_digest"] = digest(output)
    Path(args.out).write_text(json.dumps(output, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": output["pass"], "speedups": [(r["seed"], r["measured_wall_speedup"], r["conservative_p05_over_p95_wall_speedup"]) for r in records]}, sort_keys=True))
    if not output["pass"]: raise SystemExit(2)


if __name__ == "__main__":
    main()
