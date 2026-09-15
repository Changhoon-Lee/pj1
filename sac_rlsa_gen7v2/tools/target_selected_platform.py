#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sac_gen7.state_machine import verify


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def quantile(values: list[int], p: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), p, method="linear"))


def invoke(oracle: Path, target_dir: Path, report: dict, indices: Path, out: Path, threads: int) -> dict:
    command = [
        str(oracle), "--model", str(target_dir / report["files"]["model_bin"]["path"]),
        "--x", str(target_dir / report["files"]["x"]["path"]), "--y", str(target_dir / report["files"]["y"]["path"]),
        "--reported-loss", str(target_dir / report["files"]["reported_loss"]["path"]),
        "--reported-raw", str(target_dir / report["files"]["reported_raw"]["path"]),
        "--n", str(report["population"]), "--raw-tol", "0",
        "--loss-tol", str(report["numeric_tolerance"]["producer_vs_independent_loss_abs"]),
        "--threads", str(threads), "--indices", str(indices), "--out", str(out),
    ]
    started = time.perf_counter_ns()
    subprocess.run(command, check=True, capture_output=True, text=True)
    record = json.loads(out.read_text(encoding="utf-8"))
    record["external_wall_ns"] = time.perf_counter_ns() - started
    return record


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--freeze-a", required=True); p.add_argument("--state2", required=True)
    p.add_argument("--artifact-root", required=True); p.add_argument("--freeze-root", required=True)
    p.add_argument("--oracle", required=True); p.add_argument("--out", required=True)
    p.add_argument("--warmups", type=int, default=2); p.add_argument("--runs", type=int, default=11)
    args = p.parse_args()
    freeze_a = json.loads(Path(args.freeze_a).read_text(encoding="utf-8"))
    state2 = json.loads(Path(args.state2).read_text(encoding="utf-8")); verify(state2)
    if state2["state"] != 2 or state2["target_truth_accessed"]:
        raise RuntimeError("selected runner requires STATE_2 with no truth access")
    if state2["freeze_a_sha256"] != freeze_a["freeze_a_sha256"] or state2["target_seeds"] != freeze_a["untouched_target_seeds"]:
        raise RuntimeError("STATE_2 is not bound to authoritative Freeze A")
    frozen_alpha = float(freeze_a["scientific_rules"]["risk_alpha"])
    frozen_salt = str(freeze_a["freeze_a_sha256"])
    artifact_root = Path(args.artifact_root); freeze_root = Path(args.freeze_root); oracle = Path(args.oracle).resolve()
    records = []
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        for target in freeze_a["untouched_targets"]:
            seed = int(target["seed"]); target_id = target["target_id"]
            target_dir = artifact_root / f"seed{seed}"; report_path = target_dir / f"{target_id}.SCIENTIFIC_TARGET_REPORT.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            freeze_b = json.loads((freeze_root / f"FREEZE_B_SEED{seed}.json").read_text(encoding="utf-8"))
            freeze_c = json.loads((freeze_root / f"FREEZE_C_SEED{seed}.json").read_text(encoding="utf-8"))
            indices = freeze_root / f"FREEZE_C_SEED{seed}.indices.u32"
            candidate = dict(report); stored = candidate.pop("canonical_report_digest")
            checks = {
                "report_self_digest": digest(candidate) == stored,
                "freeze_b_report_digest": stored == freeze_b["target_report_digest"],
                "freeze_b_report_file": sha(report_path) == freeze_b["target_report_file_sha256"],
                "freeze_b_risk_alpha": float(freeze_b["risk_limit"]) == frozen_alpha,
                "freeze_c_to_b": freeze_c["freeze_b_sha256"] == freeze_b["freeze_b_sha256"],
                "freeze_c_public_salt": freeze_c["public_salt"] == frozen_salt,
                "indices": sha(indices) == freeze_c["indices_sha256"],
                "theory_class": freeze_b["theory_class"] == "30X_CERTIFIED",
                "oracle": oracle.is_file(),
            }
            for key, value in report["files"].items():
                checks[f"artifact_{key}"] = sha(target_dir / value["path"]) == value["sha256"] == freeze_b["artifact_hashes"][key]
            if not all(checks.values()): raise RuntimeError(f"selected binding failure seed {seed}: {checks}")
            for i in range(args.warmups): invoke(oracle, target_dir, report, indices, work / f"{seed}.warm{i}.json", 4)
            runs = [invoke(oracle, target_dir, report, indices, work / f"{seed}.run{i}.json", 4) for i in range(args.runs)]
            walls = [record["external_wall_ns"] for record in runs]
            record = {
                "seed": seed, "target_id": target_id, "report_digest": stored,
                "freeze_b_sha256": freeze_b["freeze_b_sha256"], "freeze_c_sha256": freeze_c["freeze_c_sha256"],
                "indices_sha256": freeze_c["indices_sha256"], "binding_checks": checks,
                "selected_external_wall_ns": walls, "selected_median_ns": float(statistics.median(walls)),
                "selected_p95_ns": quantile(walls, 0.95),
                "raw_mismatches_max": max(r["raw_mismatches"] for r in runs),
                "loss_mismatches_max": max(r["loss_interval_mismatches"] for r in runs),
                "bound_violations_max": max(r["bound_violations"] for r in runs),
                "selected_clean": all(r["raw_mismatches"] == 0 and r["loss_interval_mismatches"] == 0 and r["bound_violations"] == 0 for r in runs),
                "target_truth_accessed": False,
            }
            record["receipt_digest"] = digest(record)
            records.append(record)
    output = {
        "schema": "SAC_GEN7_SELECTED_PLATFORM_RECEIPT_V2R2", "platform": platform.platform(), "machine": platform.machine(),
        "oracle_sha256": sha(oracle), "records": records, "target_truth_accessed": False,
        "pass": all(record["selected_clean"] for record in records),
    }
    output["receipt_digest"] = digest(output)
    Path(args.out).write_text(json.dumps(output, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": output["pass"]}, sort_keys=True))
    if not output["pass"]: raise SystemExit(2)


if __name__ == "__main__":
    main()
