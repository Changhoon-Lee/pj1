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

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(obj: object) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def quantile(values: list[int], p: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), p, method="linear"))


def run(command: list[str]) -> tuple[int, subprocess.CompletedProcess[str]]:
    started = time.perf_counter_ns()
    process = subprocess.run(command, check=True, capture_output=True, text=True)
    return time.perf_counter_ns() - started, process


def oracle_once(oracle: Path, target_dir: Path, report: dict, indices: Path | None, out: Path, threads: int, truth_raw: Path | None = None, truth_loss: Path | None = None) -> dict:
    command = [
        str(oracle), "--model", str(target_dir / report["files"]["model_bin"]["path"]),
        "--x", str(target_dir / report["files"]["x"]["path"]),
        "--y", str(target_dir / report["files"]["y"]["path"]),
        "--reported-loss", str(target_dir / report["files"]["reported_loss"]["path"]),
        "--reported-raw", str(target_dir / report["files"]["reported_raw"]["path"]),
        "--n", str(report["population"]), "--raw-tol", "0",
        "--loss-tol", str(report["numeric_tolerance"]["producer_vs_independent_loss_abs"]),
        "--threads", str(threads), "--out", str(out),
    ]
    if indices is not None:
        command += ["--indices", str(indices)]
    if truth_raw is not None:
        command += ["--truth-raw-out", str(truth_raw)]
    if truth_loss is not None:
        command += ["--truth-loss-out", str(truth_loss)]
    wall, process = run(command)
    record = json.loads(out.read_text(encoding="utf-8"))
    record["external_wall_ns"] = wall
    record["stderr_tail"] = process.stderr[-1000:]
    return record


def timed_cpp(oracle: Path, target_dir: Path, report: dict, indices: Path | None, threads: int, warmups: int, runs: int, work: Path, prefix: str, truth: bool) -> dict:
    for i in range(warmups):
        oracle_once(oracle, target_dir, report, indices, work / f"{prefix}.warm{i}.json", threads)
    truth_raw = work / f"{prefix}.truth_raw.f64" if truth else None
    truth_loss = work / f"{prefix}.truth_loss.f64" if truth else None
    records = []
    for i in range(runs):
        records.append(
            oracle_once(
                oracle, target_dir, report, indices, work / f"{prefix}.run{i}.json", threads,
                truth_raw if i == 0 else None, truth_loss if i == 0 else None,
            )
        )
    walls = [r["external_wall_ns"] for r in records]
    return {
        "kind": "independent_cpp", "threads": threads, "warmups": warmups, "runs": runs,
        "external_wall_ns": walls, "external_wall_median_ns": float(statistics.median(walls)),
        "external_wall_p05_ns": quantile(walls, 0.05), "external_wall_p95_ns": quantile(walls, 0.95),
        "cpu_median_ns": float(statistics.median(r["cpu_ns"] for r in records)),
        "raw_mismatches_max": max(r["raw_mismatches"] for r in records),
        "loss_interval_mismatches_max": max(r["loss_interval_mismatches"] for r in records),
        "adverse_loss_mismatches_max": max(r["adverse_loss_mismatches"] for r in records),
        "loss_bound_violations_max": max(r["bound_violations"] for r in records),
        "max_abs_raw_error": max(r["max_abs_raw_error"] for r in records),
        "max_abs_loss_error": max(r["max_abs_loss_error"] for r in records),
        "native_decision_all": all(r["native_decision"] == report["reported_decision"] for r in records),
        "peak_rss_native_units_max": max(r["peak_rss_native_units"] for r in records),
        "truth_raw_path": str(truth_raw) if truth_raw else None,
        "truth_loss_path": str(truth_loss) if truth_loss else None,
        "truth_raw_sha256": sha(truth_raw) if truth_raw else None,
        "truth_loss_sha256": sha(truth_loss) if truth_loss else None,
    }


def timed_sklearn(target_dir: Path, report_path: Path, report: dict, warmups: int, runs: int, work: Path, prefix: str) -> dict:
    script = ROOT / "tools" / "sklearn_b7.py"
    for i in range(warmups):
        run([sys.executable, str(script), "--target-dir", str(target_dir), "--report", str(report_path), "--out", str(work / f"{prefix}.warm{i}.json")])
    records, walls = [], []
    for i in range(runs):
        out = work / f"{prefix}.run{i}.json"
        wall, _ = run([sys.executable, str(script), "--target-dir", str(target_dir), "--report", str(report_path), "--out", str(out)])
        walls.append(wall)
        records.append(json.loads(out.read_text(encoding="utf-8")))
    return {
        "kind": "package_native_vectorized_sklearn", "threads": "package_default", "warmups": warmups, "runs": runs,
        "external_wall_ns": walls, "external_wall_median_ns": float(statistics.median(walls)),
        "external_wall_p05_ns": quantile(walls, 0.05), "external_wall_p95_ns": quantile(walls, 0.95),
        "cpu_median_ns": float(statistics.median(r["cpu_ns"] for r in records)),
        "raw_mismatches_max": max(r["raw_bit_mismatches"] for r in records),
        "loss_interval_mismatches_max": max(r["loss_interval_mismatches"] for r in records),
        "loss_bound_violations_max": max(r["loss_bound_violations"] for r in records),
        "max_abs_raw_error": max(r["max_abs_raw_error"] for r in records),
        "max_abs_loss_error": max(r["max_abs_loss_error"] for r in records),
        "native_decision_all": all(r["native_decision"] == report["reported_decision"] for r in records),
        "peak_rss_native_units_max": max(r["peak_rss_native_units"] for r in records),
        "truth_raw_sha256": records[0]["raw_sha256"],
    }


def canonical_truth(raw: Path, y: Path, population: int, reported: Path, out: Path, indices: Path | None, tolerance: float) -> dict:
    command = [sys.executable, str(ROOT / "tools" / "canonical_truth.py"), "--raw", str(raw), "--y", str(y), "--population", str(population), "--reported-loss", str(reported), "--tolerance", str(tolerance), "--out", str(out)]
    if indices is not None:
        command += ["--indices", str(indices)]
    wall, _ = run(command)
    record = json.loads(out.read_text(encoding="utf-8"))
    record["external_wall_ns"] = wall
    return record


def binding(target_dir: Path, report_path: Path, report: dict, freeze_b: dict, freeze_c: dict, indices: Path, cost: dict, oracle: Path) -> dict:
    candidate = dict(report)
    stored = candidate.pop("canonical_report_digest")
    checks = {
        "history_role": report.get("evidence_role") == "HISTORY_ONLY",
        "report_self_digest": digest(candidate) == stored,
        "freeze_b_report_digest": stored == freeze_b["target_report_digest"],
        "freeze_b_report_file": sha(report_path) == freeze_b["target_report_file_sha256"],
        "policy_digest": digest(report["policy"]) == freeze_b["policy_digest"],
        "tree_digest": digest(report["tree_semantics"]) == freeze_b["tree_semantics_digest"],
        "canonical_truth_digest": digest(report["canonical_truth"]) == freeze_b["canonical_truth_spec_digest"],
        "tolerance_digest": digest(report["numeric_tolerance"]) == freeze_b["numeric_tolerance_digest"],
        "cost_digest": cost["cost_rule_digest"] == freeze_b["cost_rule_digest"],
        "freeze_c_to_b": freeze_c["freeze_b_sha256"] == freeze_b["freeze_b_sha256"],
        "indices": sha(indices) == freeze_c["indices_sha256"],
        "oracle_executable": oracle.is_file(),
    }
    for key, value in report["files"].items():
        checks[f"artifact_{key}"] = sha(target_dir / value["path"]) == value["sha256"] == freeze_b["artifact_hashes"][key]
    return {"checks": checks, "pass": all(checks.values())}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--artifact-root", required=True); p.add_argument("--freeze-root", required=True)
    p.add_argument("--oracle", required=True); p.add_argument("--out", required=True)
    p.add_argument("--warmups", type=int, default=2); p.add_argument("--runs", type=int, default=7)
    p.add_argument("--config", default=str(ROOT / "preflight" / "HISTORY_DRY_RUN_CONFIG.json"))
    args = p.parse_args()
    artifact_root = Path(args.artifact_root); freeze_root = Path(args.freeze_root); oracle = Path(args.oracle).resolve()
    config = json.loads(Path(args.config).read_text(encoding="utf-8")); cost = json.loads((freeze_root / "FROZEN_COST_RULE.json").read_text(encoding="utf-8"))
    records = []
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        for seed, target_id in zip(config["history_seeds"], config["target_ids"]):
            target_dir = artifact_root / f"seed{seed}"; report_path = target_dir / f"{target_id}.SCIENTIFIC_TARGET_REPORT.json"
            report = json.loads(report_path.read_text(encoding="utf-8")); freeze_b = json.loads((freeze_root / f"FREEZE_B_SEED{seed}.json").read_text()); freeze_c = json.loads((freeze_root / f"FREEZE_C_SEED{seed}.json").read_text()); indices = freeze_root / f"FREEZE_C_SEED{seed}.indices.u32"
            bind = binding(target_dir, report_path, report, freeze_b, freeze_c, indices, cost, oracle)
            if not bind["pass"]: raise RuntimeError(f"binding failure {seed}: {bind}")
            selected = timed_cpp(oracle, target_dir, report, indices, 4, args.warmups, args.runs, work, f"{seed}.selected", False)
            selected_receipt = digest(selected)
            if selected["raw_mismatches_max"] or selected["loss_interval_mismatches_max"] or selected["loss_bound_violations_max"]: raise RuntimeError(f"selected mismatch {seed}")
            # Full truth is deliberately inaccessible until the selected receipt above is closed.
            cpp1 = timed_cpp(oracle, target_dir, report, None, 1, args.warmups, args.runs, work, f"{seed}.cpp1", True)
            cpp4 = timed_cpp(oracle, target_dir, report, None, 4, args.warmups, args.runs, work, f"{seed}.cpp4", True)
            sklearn = timed_sklearn(target_dir, report_path, report, args.warmups, args.runs, work, f"{seed}.sklearn")
            modes = {"independent_cpp_1thread": cpp1, "independent_cpp_4thread": cpp4, "package_native_vectorized_sklearn": sklearn}
            strongest_name = min(modes, key=lambda name: modes[name]["external_wall_median_ns"]); strongest = modes[strongest_name]
            canonical_full = canonical_truth(Path(cpp1["truth_raw_path"]), target_dir / report["files"]["y"]["path"], report["population"], target_dir / report["files"]["reported_loss"]["path"], work / f"{seed}.canonical.json", None, report["numeric_tolerance"]["canonical_decimal_vs_reported_loss_abs"])
            canonical_selected = canonical_truth(Path(cpp1["truth_raw_path"]), target_dir / report["files"]["y"]["path"], report["population"], target_dir / report["files"]["reported_loss"]["path"], work / f"{seed}.selected_canonical.json", indices, report["numeric_tolerance"]["canonical_decimal_vs_reported_loss_abs"])
            exact_raw = all(mode["raw_mismatches_max"] == 0 and mode["truth_raw_sha256"] == report["files"]["reported_raw"]["sha256"] for mode in (cpp1, cpp4)) and sklearn["raw_mismatches_max"] == 0 and sklearn["truth_raw_sha256"] == report["files"]["reported_raw"]["sha256"]
            native_loss = all(mode["loss_interval_mismatches_max"] == 0 and mode["loss_bound_violations_max"] == 0 for mode in (cpp1, cpp4, sklearn))
            speed = strongest["external_wall_median_ns"] / selected["external_wall_median_ns"]
            conservative = min(mode["external_wall_p05_ns"] for mode in modes.values()) / selected["external_wall_p95_ns"]
            record = {
                "target_id": target_id, "seed": seed, "binding": bind, "report_digest": report["canonical_report_digest"],
                "freeze_b_sha256": freeze_b["freeze_b_sha256"], "freeze_c_sha256": freeze_c["freeze_c_sha256"],
                "indices_sha256": freeze_c["indices_sha256"], "theory_class": freeze_b["theory_class"],
                "selected_receipt_sha256": selected_receipt, "selected": selected, "selected_before_full": True,
                "complete_b7": modes, "complete_b7_executed": set(modes) == {"independent_cpp_1thread", "independent_cpp_4thread", "package_native_vectorized_sklearn"},
                "strongest_b7_mode": strongest_name, "measured_wall_speedup": speed,
                "conservative_p05_over_p95_wall_speedup": conservative, "exact_raw_truth_agreement": exact_raw,
                "native_loss_tolerance_agreement": native_loss, "canonical_truth": canonical_full,
                "selected_canonical_truth": canonical_selected, "canonical_decision_agreement": canonical_full["decision"] == report["reported_decision"],
                "unit_truth_zero_mismatch": exact_raw and native_loss and canonical_full["reported_loss_mismatches"] == 0,
                "strict_raw_truth_sha256": cpp1["truth_raw_sha256"],
                "target_bytes_digest": hashlib.sha256("".join(v["sha256"] for _, v in sorted(report["files"].items())).encode("ascii")).hexdigest(),
                "predicted_cost_upper_respected": selected["external_wall_median_ns"] <= freeze_b["predicted_rlsa_wall_upper_ns"],
            }
            record["pass"] = all([bind["pass"], freeze_b["theory_class"] == "30X_CERTIFIED", exact_raw, native_loss, canonical_full["reported_loss_mismatches"] == 0, canonical_full["decision"] == report["reported_decision"], speed >= 30, conservative >= 10])
            records.append(record)
    output = {
        "schema": "SAC_GEN7_HISTORY_PLATFORM_DRY_RUN_RECEIPT_V2", "platform": platform.platform(), "machine": platform.machine(), "python": sys.version.split()[0],
        "oracle_executable_sha256": sha(oracle), "oracle_source_sha256": sha(ROOT / "native" / "gb_oracle.cpp"), "records": records,
        "peak_rss_native_units": max(max(mode["peak_rss_native_units_max"] for mode in record["complete_b7"].values()) for record in records),
        "pass": all(record["pass"] for record in records),
    }
    output["receipt_sha256"] = digest(output)
    Path(args.out).write_text(json.dumps(output, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": output["pass"], "records": [(r["seed"], r["measured_wall_speedup"], r["conservative_p05_over_p95_wall_speedup"]) for r in records]}))
    if not output["pass"]: raise SystemExit(2)


if __name__ == "__main__":
    main()
