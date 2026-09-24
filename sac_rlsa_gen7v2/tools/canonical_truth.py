#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import decimal
import hashlib
import json
import multiprocessing as mp
import os
import time
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from pathlib import Path

import numpy as np

PRECISION = 80
PLACES = 40
LINE_BYTES = PLACES + 3
QUANTUM = Decimal(1).scaleb(-PLACES)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_decimal_loss(signed_raw: float) -> Decimal:
    if not np.isfinite(signed_raw):
        raise ValueError("nonfinite raw")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        z = Decimal.from_float(float(signed_raw))
        if z >= 0:
            value = z + (Decimal(1) + (-z).exp()).ln()
        else:
            value = (Decimal(1) + z.exp()).ln()
        q = value.quantize(QUANTUM, rounding=ROUND_HALF_EVEN)
        return abs(q) if q.is_zero() else q


def serialize_decimal(value: Decimal) -> bytes:
    text = format(value, f".{PLACES}f")
    if "e" in text.lower():
        raise RuntimeError("exponent notation forbidden")
    if text.startswith("-0.") and set(text[1:].replace(".", "")) <= {"0"}:
        text = text[1:]
    whole, frac = text.split(".")
    if len(whole) != 1 or len(frac) != PLACES:
        raise RuntimeError(f"fixed-width canonical line violation: {text}")
    encoded = (whole + "." + frac + "\n").encode("ascii")
    if len(encoded) != LINE_BYTES:
        raise RuntimeError("canonical line byte width violation")
    return encoded


def _chunk_job(payload: tuple[int, list[float], list[int]]) -> tuple[int, bytes, str, bytes]:
    start, values, counts = payload
    block = bytearray()
    floats = np.empty(len(values), dtype="<f8")
    partial = Decimal(0)
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        for i, (raw, count) in enumerate(zip(values, counts)):
            q = canonical_decimal_loss(raw)
            block.extend(serialize_decimal(q))
            floats[i] = float(q)
            partial += q * int(count)
    return start, bytes(block), format(partial, "f"), floats.tobytes()


def build_unique_table(unique: np.ndarray, counts: np.ndarray, workers: int, chunk_size: int) -> tuple[np.ndarray, np.ndarray, Decimal]:
    encoded = np.empty(unique.size, dtype=f"S{LINE_BYTES}")
    numeric = np.empty(unique.size, dtype="<f8")
    payloads = [(start, unique[start:start+chunk_size].tolist(), counts[start:start+chunk_size].tolist()) for start in range(0, unique.size, chunk_size)]
    partials: list[tuple[int, str]] = []
    if workers <= 1 or len(payloads) == 1:
        results = map(_chunk_job, payloads)
        for start, block, partial, float_bytes in results:
            n = len(block) // LINE_BYTES
            encoded[start:start+n] = np.frombuffer(block, dtype=f"S{LINE_BYTES}")
            numeric[start:start+n] = np.frombuffer(float_bytes, dtype="<f8")
            partials.append((start, partial))
    else:
        ctx = mp.get_context("spawn")
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
            futures = [pool.submit(_chunk_job, payload) for payload in payloads]
            for future in concurrent.futures.as_completed(futures):
                start, block, partial, float_bytes = future.result()
                n = len(block) // LINE_BYTES
                encoded[start:start+n] = np.frombuffer(block, dtype=f"S{LINE_BYTES}")
                numeric[start:start+n] = np.frombuffer(float_bytes, dtype="<f8")
                partials.append((start, partial))
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = ROUND_HALF_EVEN
        total = sum((Decimal(text) for _, text in sorted(partials)), Decimal(0))
    return encoded, numeric, total


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--raw", required=True)
    p.add_argument("--y", required=True)
    p.add_argument("--population", type=int, required=True)
    p.add_argument("--indices")
    p.add_argument("--reported-loss")
    p.add_argument("--tolerance", type=float, default=1.1e-10)
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--chunk-size", type=int, default=8192)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    started = time.perf_counter_ns()
    raw_path = Path(args.raw); y_path = Path(args.y)
    raw_full = np.memmap(raw_path, dtype="<f8", mode="r")
    y_full = np.memmap(y_path, dtype="<f8", mode="r", shape=(args.population,))
    indices = np.fromfile(args.indices, dtype="<u4") if args.indices else None
    if indices is None:
        if raw_full.size != args.population: raise RuntimeError("full raw size mismatch")
        raw = np.asarray(raw_full, dtype=np.float64); labels = np.asarray(y_full > 0, dtype=np.bool_)
    else:
        raw = np.asarray(raw_full if raw_full.size == indices.size else raw_full[indices], dtype=np.float64)
        labels = np.asarray(y_full[indices] > 0, dtype=np.bool_)
    if not np.isfinite(raw).all(): raise RuntimeError("NaN/Inf fail-closed")
    signed = raw.copy(); signed[labels] *= -1.0
    unique, inverse, counts = np.unique(signed, return_inverse=True, return_counts=True)
    workers = max(1, min(int(args.workers), os.cpu_count() or 1))
    encoded_unique, canonical_float_unique, total = build_unique_table(unique, counts, workers, int(args.chunk_size))
    h = hashlib.sha256(); row_chunk = 1 << 18
    for start in range(0, inverse.size, row_chunk):
        h.update(encoded_unique[inverse[start:start+row_chunk]].tobytes())
    with localcontext() as ctx:
        ctx.prec = PRECISION; ctx.rounding = ROUND_HALF_EVEN
        mean = (total / int(inverse.size)).quantize(QUANTUM, rounding=ROUND_HALF_EVEN)
        mean = abs(mean) if mean.is_zero() else mean
        threshold_decimal = Decimal(str(args.threshold)).quantize(QUANTUM, rounding=ROUND_HALF_EVEN)
    mean_text = serialize_decimal(mean).decode("ascii").rstrip("\n")
    threshold_text = serialize_decimal(threshold_decimal).decode("ascii").rstrip("\n")
    mismatch_count = adverse_count = None; max_abs_error = None
    if args.reported_loss:
        reported_full = np.memmap(args.reported_loss, dtype="<f8", mode="r", shape=(args.population,))
        reported = np.asarray(reported_full if indices is None else reported_full[indices], dtype=np.float64)
        canonical_float = canonical_float_unique[inverse]
        delta = canonical_float - reported
        mismatch_count = int(np.count_nonzero(np.abs(delta) > args.tolerance)); adverse_count = int(np.count_nonzero(delta > args.tolerance)); max_abs_error = float(np.max(np.abs(delta))) if delta.size else 0.0
    record = {
        "schema":"SAC_GEN7_DECIMAL40_CANONICAL_TRUTH_V3","count":int(inverse.size),"population":int(args.population),"indices_sha256":sha256_file(Path(args.indices)) if args.indices else None,"raw_binary64_sha256":sha256_file(raw_path),"canonical_loss_lines_sha256":h.hexdigest(),"canonical_mean_string":mean_text,"threshold_string":threshold_text,"decision":bool(mean < Decimal(str(args.threshold))),"decimal_context_precision":PRECISION,"decimal_rounding":"ROUND_HALF_EVEN","decimal_places":PLACES,"libmpdec_version":getattr(decimal,"__libmpdec_version__",None),"serialization":"ASCII fixed point, exactly 40 fractional digits, trailing zeros retained, no exponent, -0 normalized to 0, LF, original row order","unique_signed_raw_values":int(unique.size),"reported_loss_tolerance":args.tolerance if args.reported_loss else None,"reported_loss_mismatches":mismatch_count,"reported_adverse_mismatches":adverse_count,"max_abs_reported_loss_error":max_abs_error,"workers":workers,"chunk_size":int(args.chunk_size),"wall_ns":time.perf_counter_ns()-started,
    }
    Path(args.out).write_text(json.dumps(record,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"decision":record["decision"],"digest":record["canonical_loss_lines_sha256"],"mean":mean_text,"workers":workers},sort_keys=True))

if __name__ == "__main__": main()
