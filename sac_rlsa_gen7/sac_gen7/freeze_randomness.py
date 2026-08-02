from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np

from .common import digest_obj, write_json


def freeze(freeze_b_path: Path, out_path: Path, salt: str) -> dict:
    freeze_b = json.loads(freeze_b_path.read_text(encoding="utf-8"))
    seed128 = int.from_bytes(
        hashlib.sha256((freeze_b["freeze_b_sha256"] + "|" + salt).encode("utf-8")).digest()[:16],
        "big",
    )
    rng = np.random.Generator(np.random.PCG64DXSM(seed128))
    indices = np.sort(
        rng.choice(
            freeze_b["population"],
            size=freeze_b["sample_size"],
            replace=False,
        ).astype(np.uint32)
    )
    binary = b"".join(struct.pack("<I", int(x)) for x in indices)
    record = {
        "schema": "SAC_GEN7_FREEZE_C_V1",
        "target_id": freeze_b["target_id"],
        "freeze_b_sha256": freeze_b["freeze_b_sha256"],
        "public_salt": salt,
        "seed_128": seed128,
        "sample_size": int(indices.size),
        "indices": [int(x) for x in indices],
        "indices_binary_sha256": hashlib.sha256(binary).hexdigest(),
        "truth_accessed": False,
    }
    record["freeze_c_sha256"] = digest_obj(record)
    write_json(out_path, record)
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-b", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--salt", required=True)
    args = parser.parse_args()
    record = freeze(Path(args.freeze_b), Path(args.out), args.salt)
    print(record["freeze_c_sha256"])


if __name__ == "__main__":
    main()
