#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT.parent
sys.path.insert(0, str(PYTHON_ROOT))

from sac_rlsa_gen7.sac_gen7.common import digest_obj, sha256_file, write_json
from sac_rlsa_gen7.sac_gen7.certify import certify
from sac_rlsa_gen7.sac_gen7.freeze_randomness import freeze
from sac_rlsa_gen7.sac_gen7.reporter import generate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--public-root", required=True)
    parser.add_argument("--freeze-a-commit", required=True)
    parser.add_argument("--out-manifest", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    source_root = repo_root / "sac_rlsa_gen7"
    freeze_root = source_root / "freeze"
    artifact_root = Path(args.artifact_root)
    public_root = Path(args.public_root)
    artifact_freeze = artifact_root / "freeze"
    public_freeze = public_root / "freeze"
    public_reports = public_root / "target_reports"
    public_receipts = public_root / "generation_receipts"
    for path in (artifact_root, artifact_freeze, public_freeze, public_reports, public_receipts):
        path.mkdir(parents=True, exist_ok=True)

    freeze_a = json.loads((freeze_root / "FREEZE_A_POLICY_ORACLE_COST.json").read_text(encoding="utf-8"))
    cost_path = freeze_root / "FROZEN_COST_RULE.json"
    cost = json.loads(cost_path.read_text(encoding="utf-8"))
    if freeze_a["cost_rule"]["cost_rule_digest"] != cost["cost_rule_digest"]:
        raise RuntimeError("Freeze-A cost-rule digest mismatch")
    if freeze_a["target_truth_accessed"] or freeze_a["target_report_accessed"]:
        raise RuntimeError("Freeze-A leakage flag")
    for name in ("FREEZE_A_POLICY_ORACLE_COST.json", "FROZEN_COST_RULE.json", "SEED_SELECTION_RULE.json"):
        shutil.copy2(freeze_root / name, artifact_freeze / name)
        shutil.copy2(freeze_root / name, public_freeze / name)

    records = []
    for target in freeze_a["untouched_targets"]:
        seed = int(target["seed"])
        target_id = target["target_id"]
        target_dir = artifact_root / f"seed{seed}"
        report = generate(target_dir, target_id, seed, int(target["population"]))
        report_path = target_dir / f"{target_id}.SCIENTIFIC_REPORT.json"
        generation_path = target_dir / f"{target_id}.GENERATION_RECEIPT.json"
        shutil.copy2(report_path, public_reports / report_path.name)
        shutil.copy2(generation_path, public_receipts / generation_path.name)

        freeze_b_path = artifact_freeze / f"FREEZE_B_SEED{seed}.json"
        freeze_b = certify(report_path, cost_path, freeze_b_path)
        if freeze_b["theory_class"] != "30X_CERTIFIED":
            raise RuntimeError(f"seed {seed} failed pre-truth 30X certification")
        shutil.copy2(freeze_b_path, public_freeze / freeze_b_path.name)

        freeze_c_path = artifact_freeze / f"FREEZE_C_SEED{seed}.json"
        public_salt = args.freeze_a_commit + "|SAC-RLSA-GEN7-FREEZE-C-V1"
        freeze_c = freeze(freeze_b_path, freeze_c_path, public_salt)
        shutil.copy2(freeze_c_path, public_freeze / freeze_c_path.name)

        records.append(
            {
                "seed": seed,
                "target_id": target_id,
                "canonical_report_digest": report["canonical_report_digest"],
                "public_report_sha256": sha256_file(report_path),
                "freeze_b_sha256": freeze_b["freeze_b_sha256"],
                "freeze_c_sha256": freeze_c["freeze_c_sha256"],
                "indices_binary_sha256": freeze_c["indices_binary_sha256"],
                "theory_class": freeze_b["theory_class"],
                "target_truth_accessed": False,
            }
        )

    trigger = {
        "schema": "SAC_GEN7_PUBLIC_FREEZE_BC_TRIGGER_V1",
        "freeze_a_public_commit": args.freeze_a_commit,
        "freeze_a_sha256": freeze_a["freeze_a_sha256"],
        "records": records,
        "target_truth_accessed": False,
    }
    trigger["freeze_bc_bundle_sha256"] = digest_obj(trigger)
    write_json(artifact_freeze / "FREEZE_BC_TRIGGER.json", trigger)
    write_json(public_freeze / "FREEZE_BC_TRIGGER.json", trigger)

    manifest_files = []
    for path in sorted(artifact_root.rglob("*")):
        if path.is_file():
            manifest_files.append(
                {
                    "path": path.relative_to(artifact_root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    manifest = {
        "schema": "SAC_GEN7_TARGET_ARTIFACT_MANIFEST_V1",
        "freeze_a_public_commit": args.freeze_a_commit,
        "freeze_bc_bundle_sha256": trigger["freeze_bc_bundle_sha256"],
        "files": manifest_files,
        "target_truth_accessed": False,
    }
    manifest["manifest_digest"] = digest_obj(manifest)
    write_json(Path(args.out_manifest), manifest)
    print(json.dumps({"records": records, "manifest_digest": manifest["manifest_digest"]}, sort_keys=True))


if __name__ == "__main__":
    main()
