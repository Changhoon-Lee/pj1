#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sac_gen7.qualification_roles import reclassify_record


def digest(obj: object) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    output = dict(source)
    output["schema"] = "SAC_GEN7_ROLE_SEPARATED_PLATFORM_RECEIPT_V1"
    output["source_receipt_sha256"] = digest(source)
    output["protocol"] = "CANONICAL_ORACLE_AND_B7_COMPARATOR_SEPARATED"
    output["records"] = [reclassify_record(record) for record in source["records"]]
    output["pass"] = all(record["pass"] for record in output["records"])
    output.pop("receipt_sha256", None)
    output["receipt_sha256"] = digest(output)
    Path(args.out).write_text(
        json.dumps(output, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "pass": output["pass"],
                "records": [
                    (
                        r["seed"],
                        r["canonical_oracle_qualification"]["pass"],
                        r["b7_portfolio_qualification"]["pass"],
                        r["measured_wall_speedup"],
                    )
                    for r in output["records"]
                ],
            },
            sort_keys=True,
        )
    )
    if not output["pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
