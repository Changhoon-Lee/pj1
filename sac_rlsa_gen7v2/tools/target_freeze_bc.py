#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sac_gen7.certify import certify
from sac_gen7.common import digest_obj, write_json
from sac_gen7.freeze_randomness import freeze
from sac_gen7.state_machine import transition, verify


FROZEN_RANDOMNESS_RULE = "uniform without replacement from Freeze-A content digest and Freeze-B digest"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--freeze-a", required=True); p.add_argument("--state1", required=True)
    p.add_argument("--artifact-root", required=True); p.add_argument("--freeze-root", required=True)
    p.add_argument("--cost-rule", required=True); p.add_argument("--out-state2", required=True)
    p.add_argument("--out-bundle", required=True)
    args = p.parse_args()
    freeze_a = json.loads(Path(args.freeze_a).read_text(encoding="utf-8"))
    state1 = json.loads(Path(args.state1).read_text(encoding="utf-8")); verify(state1)
    if state1["state"] != 1 or state1["target_truth_accessed"]:
        raise RuntimeError("STATE_1 with no truth access required")
    if freeze_a["freeze_a_sha256"] != state1["freeze_a_sha256"] or freeze_a["untouched_target_seeds"] != state1["target_seeds"]:
        raise RuntimeError("Freeze A to STATE_1 mismatch")

    scientific_rules = freeze_a.get("scientific_rules", {})
    if scientific_rules.get("audit_randomness") != FROZEN_RANDOMNESS_RULE:
        raise RuntimeError("Freeze A audit-randomness rule mismatch")
    alpha = float(scientific_rules["risk_alpha"])
    if not (0.0 < alpha < 1.0):
        raise RuntimeError("invalid frozen risk alpha")
    # The authority explicitly freezes the content digest—not a self-referential commit SHA—as the public salt.
    public_salt = str(freeze_a["freeze_a_sha256"])

    artifact_root = Path(args.artifact_root); freeze_root = Path(args.freeze_root); freeze_root.mkdir(parents=True, exist_ok=True)
    records = []
    for target in freeze_a["untouched_targets"]:
        seed = int(target["seed"]); target_id = target["target_id"]
        report_path = artifact_root / f"seed{seed}" / f"{target_id}.SCIENTIFIC_TARGET_REPORT.json"
        freeze_b_path = freeze_root / f"FREEZE_B_SEED{seed}.json"
        freeze_c_path = freeze_root / f"FREEZE_C_SEED{seed}.json"
        indices_path = freeze_root / f"FREEZE_C_SEED{seed}.indices.u32"
        freeze_b = certify(report_path, Path(args.cost_rule), freeze_b_path, alpha)
        if freeze_b["theory_class"] != "30X_CERTIFIED":
            raise RuntimeError(f"seed {seed} not pretruth 30X: {freeze_b['theory_class']}")
        freeze_c = freeze(freeze_b_path, freeze_c_path, indices_path, public_salt)
        records.append({
            "seed": seed, "target_id": target_id,
            "freeze_b_sha256": freeze_b["freeze_b_sha256"], "freeze_c_sha256": freeze_c["freeze_c_sha256"],
            "indices_sha256": freeze_c["indices_sha256"], "sample_size": freeze_b["sample_size"],
            "risk_bound": freeze_b["hypergeometric_miss_bound"], "predicted_speedup_lower": freeze_b["predicted_wall_speedup_lower"],
            "theory_class": freeze_b["theory_class"], "target_truth_accessed": False,
        })
    bundle = {
        "schema": "SAC_GEN7_PUBLIC_FREEZE_BC_BUNDLE_V2",
        "freeze_a_sha256": freeze_a["freeze_a_sha256"],
        "risk_alpha": alpha,
        "audit_randomness_public_salt": public_salt,
        "records": records,
        "target_truth_accessed": False,
    }
    bundle["freeze_bc_bundle_sha256"] = digest_obj(bundle)
    write_json(Path(args.out_bundle), bundle)
    state2 = transition(state1, 2, "FREEZE_B_C_PUBLICLY_COMMITTED_BEFORE_SELECTED_AUDIT")
    write_json(Path(args.out_state2), state2)
    print(json.dumps(bundle, sort_keys=True))


if __name__ == "__main__":
    main()
