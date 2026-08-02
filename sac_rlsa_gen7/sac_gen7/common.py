from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest_obj(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def log_hypergeom_miss(population: int, bad_support: int, sample: int) -> float:
    if not (0 <= sample <= population):
        return float("inf")
    if bad_support <= 0:
        return 0.0
    if sample > population - bad_support:
        return float("-inf")
    return (
        math.lgamma(population - bad_support + 1)
        - math.lgamma(sample + 1)
        - math.lgamma(population - bad_support - sample + 1)
        - math.lgamma(population + 1)
        + math.lgamma(sample + 1)
        + math.lgamma(population - sample + 1)
    )


def minimal_sample(population: int, bad_support: int, alpha: float) -> tuple[int, float]:
    if not (0 < alpha < 1):
        raise ValueError("alpha must lie in (0,1)")
    if bad_support <= 0:
        return population, 1.0
    lo, hi = 0, population
    target = math.log(alpha)
    while lo < hi:
        mid = (lo + hi) // 2
        if log_hypergeom_miss(population, bad_support, mid) <= target:
            hi = mid
        else:
            lo = mid + 1
    sample = lo
    miss = 0.0 if sample > population - bad_support else math.exp(
        log_hypergeom_miss(population, bad_support, sample)
    )
    return sample, miss
