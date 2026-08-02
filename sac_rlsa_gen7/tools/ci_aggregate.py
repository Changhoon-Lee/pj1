#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ubuntu", required=True)
    parser.add_argument("--macos", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    ubuntu = json.loads(Path(args.ubuntu).read_text(encoding="utf-8"))
    macos = json.loads(Path(args.macos).read_text(encoding="utf-8"))
    u_records = {int(record["seed"]): record for record in ubuntu["records"]}
    m_records = {int(record["seed"]): record for record in macos["records"]}
    if set(u_records) != set(m_records):
        raise RuntimeError("platform target-set mismatch")
    records = []
    for seed in sorted(u_records):
        u = u_records[seed]
        m = m_records[seed]
        record = {
            "seed": seed,
            "target_id": u["target_id"],
            "same_canonical_report_digest": u["canonical_report_digest"] == m["canonical_report_digest"],
            "same_freeze_b": u["freeze_b_sha256"] == m["freeze_b_sha256"],
            "same_freeze_c": u["freeze_c_sha256"] == m["freeze_c_sha256"],
            "same_target_bytes": u["target_bytes_digest"] == m["target_bytes_digest"],
            "same_strict_raw_truth_digest": u["strict_raw_truth_sha256"] == m["strict_raw_truth_sha256"],
            "same_canonical_decimal_truth_digest": u["canonical_truth"]["canonical_loss_decimal40_sha256"] == m["canonical_truth"]["canonical_loss_decimal40_sha256"],
            "same_canonical_mean": u["canonical_truth"]["mean_loss_decimal80"] == m["canonical_truth"]["mean_loss_decimal80"],
            "same_canonical_decision": u["canonical_truth"]["decision"] == m["canonical_truth"]["decision"],
            "ubuntu_pass": u["pass"],
            "macos_pass": m["pass"],
            "ubuntu_measured_wall_speedup": u["measured_wall_speedup"],
            "macos_measured_wall_speedup": m["measured_wall_speedup"],
            "ubuntu_conservative_wall_speedup": u["conservative_p05_over_p95_wall_speedup"],
            "macos_conservative_wall_speedup": m["conservative_p05_over_p95_wall_speedup"],
            "ubuntu_strongest_b7": u["strongest_b7_mode"],
            "macos_strongest_b7": m["strongest_b7_mode"],
            "ubuntu_complete_b7": u["complete_b7_executed"],
            "macos_complete_b7": m["complete_b7_executed"],
        }
        record["pass"] = all(
            [
                record["same_canonical_report_digest"],
                record["same_freeze_b"],
                record["same_freeze_c"],
                record["same_target_bytes"],
                record["same_strict_raw_truth_digest"],
                record["same_canonical_decimal_truth_digest"],
                record["same_canonical_mean"],
                record["same_canonical_decision"],
                record["ubuntu_pass"],
                record["macos_pass"],
                record["ubuntu_complete_b7"],
                record["macos_complete_b7"],
                record["ubuntu_measured_wall_speedup"] >= 30,
                record["macos_measured_wall_speedup"] >= 30,
                record["ubuntu_conservative_wall_speedup"] >= 10,
                record["macos_conservative_wall_speedup"] >= 10,
            ]
        )
        records.append(record)
    output = {
        "schema": "SAC_GEN7_CANONICAL_CROSS_PLATFORM_SUMMARY_V1",
        "ubuntu_platform": ubuntu["platform"],
        "macos_platform": macos["platform"],
        "records": records,
        "canonical_truth_mode": "REFERENCE_DECIMAL_40DP_FROM_STRICT_BINARY64_RAW",
        "pass": ubuntu["pass"] and macos["pass"] and all(record["pass"] for record in records),
    }
    Path(args.out).write_text(json.dumps(output, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if not output["pass"]:
        raise SystemExit(2)
    print(json.dumps({"pass": True}, sort_keys=True))


if __name__ == "__main__":
    main()
