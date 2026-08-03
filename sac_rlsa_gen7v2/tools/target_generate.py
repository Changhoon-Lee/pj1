#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import resource
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sac_gen7.common import digest_obj, sha256_file, write_json
from sac_gen7.reporter import generate
from sac_gen7.state_machine import transition, verify


def tree_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--freeze-a", required=True); p.add_argument("--state0", required=True)
    p.add_argument("--lease", required=True); p.add_argument("--artifact-root", required=True)
    p.add_argument("--out-state1", required=True); p.add_argument("--out-manifest", required=True)
    args = p.parse_args()
    freeze_a = json.loads(Path(args.freeze_a).read_text(encoding="utf-8"))
    state0 = json.loads(Path(args.state0).read_text(encoding="utf-8")); verify(state0)
    lease = json.loads(Path(args.lease).read_text(encoding="utf-8"))
    if state0["state"] != 0 or state0["seeds_consumed"] or not lease.get("single_use_lease_active"):
        raise RuntimeError("single-use state or lease failure")
    if freeze_a["freeze_a_sha256"] != state0["freeze_a_sha256"] or freeze_a["untouched_target_seeds"] != state0["target_seeds"]:
        raise RuntimeError("Freeze A to STATE_0 mismatch")
    if lease["freeze_a_sha256"] != state0["freeze_a_sha256"] or lease["target_seed_digest"] != state0["target_seed_digest"]:
        raise RuntimeError("lease is not bound to STATE_0")
    artifact_root = Path(args.artifact_root); artifact_root.mkdir(parents=True, exist_ok=True)
    records = []; started = time.perf_counter_ns()
    for target in freeze_a["untouched_targets"]:
        target_dir = artifact_root / f"seed{target['seed']}"
        if target_dir.exists():
            raise RuntimeError("target directory already exists; prospective seed is consumed")
        report, _ = generate(target_dir, target["target_id"], int(target["seed"]), int(target["population"]), "PROSPECTIVE_TARGET")
        report_path = target_dir / f"{target['target_id']}.SCIENTIFIC_TARGET_REPORT.json"
        records.append({
            "seed": target["seed"], "target_id": target["target_id"],
            "canonical_report_digest": report["canonical_report_digest"],
            "report_file_sha256": sha256_file(report_path),
            "artifact_hashes": {key: value["sha256"] for key, value in sorted(report["files"].items())},
            "generation_receipt_sha256": sha256_file(target_dir / f"{target['target_id']}.GENERATION_RECEIPT.json"),
            "target_truth_accessed": False,
        })
    state1 = transition(state0, 1, "TARGET_REPORTS_GENERATED_AND_HASHED; TARGET_SEEDS_PERMANENTLY_CONSUMED")
    write_json(Path(args.out_state1), state1)
    manifest = {
        "schema": "SAC_GEN7_TARGET_STATE1_MANIFEST_V2",
        "freeze_a_sha256": freeze_a["freeze_a_sha256"], "records": records,
        "artifact_bytes": tree_bytes(artifact_root), "generation_wall_ns": time.perf_counter_ns() - started,
        "peak_rss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "target_truth_accessed": False,
    }
    manifest["manifest_digest"] = digest_obj(manifest)
    write_json(Path(args.out_manifest), manifest)
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
