from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .common import digest_obj, write_json

STATES = {
    0: "PRETARGET_FROZEN",
    1: "TARGET_REPORT_GENERATED",
    2: "FREEZE_B_C_PUBLIC",
    3: "SELECTED_AUDIT_COMPLETE",
    4: "FULL_TRUTH_COMPLETE",
    5: "CROSS_PLATFORM_COMPLETE",
    6: "FINAL_ADJUDICATED",
}


def initial_state(campaign_id: str, freeze_a_sha256: str, target_seeds: list[int]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema": "SAC_GEN7_SINGLE_USE_STATE_V2",
        "campaign_id": campaign_id,
        "state": 0,
        "state_name": STATES[0],
        "freeze_a_sha256": freeze_a_sha256,
        "target_seeds": target_seeds,
        "target_seed_digest": digest_obj(target_seeds),
        "seeds_consumed": False,
        "target_reports_generated": False,
        "target_truth_accessed": False,
        "previous_state_digest": None,
        "transition_evidence": "AUTHORITATIVE_FREEZE_A_V2",
    }
    record["state_digest"] = digest_obj(record)
    return record


def verify(record: dict[str, Any]) -> None:
    candidate = dict(record)
    stored = candidate.pop("state_digest")
    if digest_obj(candidate) != stored:
        raise RuntimeError("state digest mismatch")
    state = int(record["state"])
    if state not in STATES or record["state_name"] != STATES[state]:
        raise RuntimeError("invalid state name")
    if state >= 1 and not record["seeds_consumed"]:
        raise RuntimeError("state >=1 requires consumed seeds")
    if state >= 1 and not record["target_reports_generated"]:
        raise RuntimeError("state >=1 requires target reports")
    if state < 4 and record["target_truth_accessed"]:
        raise RuntimeError("truth accessed before STATE_4")


def transition(previous: dict[str, Any], new_state: int, evidence: str) -> dict[str, Any]:
    verify(previous)
    old = int(previous["state"])
    if new_state != old + 1:
        raise RuntimeError(f"non-monotone transition {old}->{new_state}")
    if new_state not in STATES:
        raise RuntimeError("unknown target state")
    record = {k: v for k, v in previous.items() if k != "state_digest"}
    record.update(
        {
            "state": new_state,
            "state_name": STATES[new_state],
            "previous_state_digest": previous["state_digest"],
            "transition_evidence": evidence,
        }
    )
    if new_state >= 1:
        record["seeds_consumed"] = True
        record["target_reports_generated"] = True
    if new_state >= 4:
        record["target_truth_accessed"] = True
    record["state_digest"] = digest_obj(record)
    verify(record)
    return record


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--previous")
    p.add_argument("--out", required=True)
    p.add_argument("--new-state", type=int)
    p.add_argument("--evidence")
    p.add_argument("--campaign-id")
    p.add_argument("--freeze-a-sha256")
    p.add_argument("--target-seeds")
    p.add_argument("--verify", action="store_true")
    args = p.parse_args()
    if args.verify:
        record = json.loads(Path(args.previous).read_text(encoding="utf-8"))
        verify(record)
        write_json(Path(args.out), record)
        return
    if args.previous:
        previous = json.loads(Path(args.previous).read_text(encoding="utf-8"))
        record = transition(previous, int(args.new_state), str(args.evidence))
    else:
        seeds = [int(x) for x in str(args.target_seeds).split(",") if x]
        record = initial_state(str(args.campaign_id), str(args.freeze_a_sha256), seeds)
    write_json(Path(args.out), record)


if __name__ == "__main__":
    main()
