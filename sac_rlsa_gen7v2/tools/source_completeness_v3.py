#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    required = [
        "sac_gen7/common.py",
        "sac_gen7/model_io.py",
        "sac_gen7/reporter.py",
        "sac_gen7/certify.py",
        "sac_gen7/freeze_randomness.py",
        "sac_gen7/strict_math.py",
        "sac_gen7/state_machine.py",
        "sac_gen7/qualification_roles.py",
        "native/gb_oracle.cpp",
        "native/oracle_model.hpp",
        "native/oracle_selftest.hpp",
        "tools/compile_oracle.sh",
        "tools/canonical_truth.py",
        "tools/canonical_truth_selftest.py",
        "tools/sklearn_b7.py",
        "tools/reclassify_platform_receipt.py",
        "tools/history_build.py",
        "tools/history_platform_run.py",
        "tools/history_aggregate_v3.py",
        "tools/target_generate.py",
        "tools/target_freeze_bc.py",
        "tools/target_selected_platform.py",
        "tools/target_selected_aggregate.py",
        "tools/target_full_platform.py",
        "tools/target_full_aggregate.py",
        "tools/protocol_scientific_rule_diff_v3.py",
        "protocol/QUALIFICATION_PROTOCOL_V2.json",
        "protocol/SCIENTIFIC_RULE_PROJECTION_V2.json",
        "protocol/PROTOCOL_QUALIFICATION_SEPARATION.md",
        "preflight/PRIOR_GEN7_AUTHORITATIVE_PACKAGE.json",
        ".github/workflows/gen7-history-dry-run.yml",
        ".github/workflows/gen7-target-single-use.yml",
    ]
    files = {
        relative: {
            "exists": (root / relative).is_file(),
            "sha256": sha(root / relative) if (root / relative).is_file() else None,
            "bytes": (root / relative).stat().st_size if (root / relative).is_file() else None,
        }
        for relative in required
    }
    forbidden_transport = []
    for path in root.rglob("*"):
        if path.is_file() and (
            path.suffix == ".b64"
            or "source_bundle" in path.name
            or "materializer" in path.name.lower()
            or "source_chunks" in path.parts
        ):
            forbidden_transport.append(str(path.relative_to(root)))

    pretarget_forbidden = [
        "freeze/FREEZE_A_V2_AUTHORITATIVE_DIRECT_SOURCE.json",
        "freeze/TARGET_RUN_TRIGGER.json",
        "state/STATE_0.json",
        "state/STATE_1.json",
        "public_records/target_reports",
    ]
    present_pretarget_forbidden = [
        relative for relative in pretarget_forbidden if (root / relative).exists()
    ]
    prior = json.loads(
        (root / "preflight/PRIOR_GEN7_AUTHORITATIVE_PACKAGE.json").read_text(encoding="utf-8")
    ) if (root / "preflight/PRIOR_GEN7_AUTHORITATIVE_PACKAGE.json").is_file() else {}
    authoritative_identity = {
        "filename": prior.get("zip_filename"),
        "sha256": prior.get("zip_sha256"),
        "sha_is_facc": prior.get("zip_sha256") == "facc965a1533033ceef020517d0e3a4475fd64271ecdb1ef5e738070becb3993",
        "wrong_body_authorized": prior.get("wrong_or_unverified_zip_body_authorized"),
    }
    result = {
        "schema": "SAC_GEN7_DIRECT_SOURCE_COMPLETENESS_V3",
        "required_files": files,
        "forbidden_transport_artifacts": sorted(forbidden_transport),
        "base64_bundle_removed": not forbidden_transport,
        "all_required_direct_sources_present": all(value["exists"] for value in files.values()),
        "pretarget_forbidden_paths": pretarget_forbidden,
        "present_pretarget_forbidden_paths": present_pretarget_forbidden,
        "target_execution_locked": not present_pretarget_forbidden,
        "prior_authoritative_package_identity": authoritative_identity,
    }
    result["pass"] = (
        result["all_required_direct_sources_present"]
        and result["base64_bundle_removed"]
        and result["target_execution_locked"]
        and authoritative_identity["sha_is_facc"]
        and authoritative_identity["wrong_body_authorized"] is False
    )
    Path(args.out).write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "pass": result["pass"],
                "required": len(files),
                "forbidden_transport": forbidden_transport,
                "pretarget_forbidden_present": present_pretarget_forbidden,
            },
            sort_keys=True,
        )
    )
    if not result["pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
