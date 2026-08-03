#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import resource
import time
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--loss-tol", type=float, default=1.1e-10)
    args = parser.parse_args()
    started = time.perf_counter_ns()
    cpu_started = time.process_time_ns()
    target_dir = Path(args.target_dir)
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    population = int(report["population"])
    x = np.memmap(target_dir / report["files"]["x"]["path"], dtype="<f8", mode="r", shape=(population, 10))
    y = np.memmap(target_dir / report["files"]["y"]["path"], dtype="<f8", mode="r", shape=(population,))
    reported_raw = np.memmap(target_dir / report["files"]["reported_raw"]["path"], dtype="<f8", mode="r", shape=(population,))
    reported_loss = np.memmap(target_dir / report["files"]["reported_loss"]["path"], dtype="<f8", mode="r", shape=(population,))
    with (target_dir / report["files"]["model_pickle"]["path"]).open("rb") as f:
        model = pickle.load(f)
    raw = np.asarray(model.decision_function(x), dtype="<f8")
    loss = np.asarray(np.logaddexp(0.0, raw) - (y > 0).astype(np.float64) * raw, dtype="<f8")
    raw_bit_mismatches = int(np.count_nonzero(raw.view("<u8") != reported_raw.view("<u8")))
    loss_mismatches = int(np.count_nonzero(np.abs(loss - reported_loss) > args.loss_tol))
    mean_loss = float(np.mean(loss))
    record = {
        "schema": "SAC_GEN7_SKLEARN_B7_V2",
        "population": population,
        "raw_bit_mismatches": raw_bit_mismatches,
        "loss_interval_mismatches": loss_mismatches,
        "loss_bound_violations": int(np.count_nonzero(loss > float(report["model_bounds"]["loss_upper_binary64"]))),
        "max_abs_raw_error": float(np.max(np.abs(raw - reported_raw))),
        "max_abs_loss_error": float(np.max(np.abs(loss - reported_loss))),
        "raw_sha256": hashlib.sha256(np.ascontiguousarray(raw, dtype="<f8").tobytes()).hexdigest(),
        "mean_native_loss": mean_loss,
        "native_decision": bool(mean_loss < report["policy"]["threshold"]),
        "wall_ns": time.perf_counter_ns() - started,
        "cpu_ns": time.process_time_ns() - cpu_started,
        "peak_rss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "implementation": "scikit-learn 1.8.0 vectorized decision_function, frozen model pickle",
    }
    Path(args.out).write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
