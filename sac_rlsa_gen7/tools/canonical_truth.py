#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path

import numpy as np


def decimal_loss(raw: float, positive: bool) -> Decimal:
    value = Decimal.from_float(float(raw))
    one = Decimal(1)
    if value > 0:
        loss = value + (one + (-value).exp()).ln()
    else:
        loss = (one + value.exp()).ln()
    if positive:
        loss -= value
    return loss


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True)
    parser.add_argument("--y", required=True)
    parser.add_argument("--population", type=int, required=True)
    parser.add_argument("--threshold", type=str, default="0.5")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    started = time.perf_counter_ns()
    raw_path = Path(args.raw)
    y_path = Path(args.y)
    raw = np.memmap(raw_path, dtype="<f8", mode="r", shape=(args.population,))
    y = np.memmap(y_path, dtype="<f8", mode="r", shape=(args.population,))
    digest = hashlib.sha256()
    total = Decimal(0)
    quantum = Decimal("1e-40")
    with localcontext() as ctx:
        ctx.prec = 80
        for raw_value, label in zip(raw, y):
            loss = decimal_loss(float(raw_value), bool(label > 0))
            total += loss
            canonical = loss.quantize(quantum, rounding=ROUND_HALF_EVEN)
            digest.update((format(canonical, ".40f") + "\n").encode("ascii"))
        mean = total / Decimal(args.population)
    record = {
        "schema": "SAC_GEN7_REFERENCE_DECIMAL_TRUTH_V1",
        "population": args.population,
        "raw_binary64_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "canonical_loss_decimal40_sha256": digest.hexdigest(),
        "mean_loss_decimal80": format(mean, "f"),
        "threshold_decimal": args.threshold,
        "decision": bool(mean < Decimal(args.threshold)),
        "decimal_context_precision": 80,
        "per_unit_serialization": "fixed 40 digits after decimal, ROUND_HALF_EVEN, newline",
        "wall_ns": time.perf_counter_ns() - started,
    }
    Path(args.out).write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
