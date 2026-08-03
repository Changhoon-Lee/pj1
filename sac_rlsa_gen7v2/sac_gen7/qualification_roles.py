from __future__ import annotations

from typing import Any


def _strict_modes(modes: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    return [(name, mode) for name, mode in modes.items() if mode.get("kind") == "independent_cpp"]


def qualify_canonical_oracle(record: dict[str, Any]) -> dict[str, Any]:
    """Canonical scientific truth is strict C++ plus Decimal-40, never package-native B7."""
    modes = record["complete_b7"]
    strict = _strict_modes(modes)
    raw_digests = [mode.get("truth_raw_sha256") for _, mode in strict]
    canonical = record["canonical_truth"]
    checks = {
        "two_strict_cpp_modes": len(strict) == 2,
        "strict_cpp_raw_exact_to_frozen_report": len(strict) == 2
        and all(mode.get("raw_mismatches_max") == 0 for _, mode in strict),
        "strict_cpp_raw_digest_identity": len(set(raw_digests)) == 1
        and None not in raw_digests,
        "strict_cpp_loss_within_frozen_tolerance": len(strict) == 2
        and all(mode.get("loss_interval_mismatches_max") == 0 for _, mode in strict),
        "strict_cpp_loss_bound": len(strict) == 2
        and all(mode.get("loss_bound_violations_max") == 0 for _, mode in strict),
        "strict_cpp_decision": len(strict) == 2
        and all(mode.get("native_decision_all") is True for _, mode in strict),
        "decimal40_reported_loss_tolerance": canonical.get("reported_loss_mismatches") == 0,
        "decimal40_decision": record.get("canonical_decision_agreement", True),
    }
    return {
        "schema": "SAC_GEN7_CANONICAL_ORACLE_QUALIFICATION_V1",
        "role": "scientific_adjudication_truth",
        "checks": checks,
        "pass": all(checks.values()),
    }


def qualify_b7_mode(name: str, mode: dict[str, Any]) -> dict[str, Any]:
    common = {
        "loss_within_frozen_tolerance": mode.get("loss_interval_mismatches_max") == 0,
        "loss_within_strict_upper_bound": mode.get("loss_bound_violations_max") == 0,
        "decision_matches_frozen_policy": mode.get("native_decision_all") is True,
    }
    if mode.get("kind") == "independent_cpp":
        role_checks = {"raw_exact_required_for_strict_cpp": mode.get("raw_mismatches_max") == 0}
        equivalence = "EXACT_STRICT_ORACLE_COMPATIBLE"
    else:
        role_checks = {
            "raw_bit_identity_is_diagnostic_only": True,
            "raw_bit_mismatch_count_recorded": isinstance(mode.get("raw_mismatches_max"), int),
        }
        equivalence = "FROZEN_TOLERANCE_AND_DECISION_EQUIVALENT"
    checks = {**common, **role_checks}
    return {
        "mode": name,
        "role": "strongest_deployable_full_audit_cost_comparator",
        "equivalence_class": equivalence,
        "raw_bit_mismatches_diagnostic": mode.get("raw_mismatches_max"),
        "max_abs_raw_error_diagnostic": mode.get("max_abs_raw_error"),
        "max_abs_loss_error": mode.get("max_abs_loss_error"),
        "checks": checks,
        "pass": all(checks.values()),
    }


def qualify_b7_portfolio(record: dict[str, Any]) -> dict[str, Any]:
    modes = record["complete_b7"]
    qualifications = {name: qualify_b7_mode(name, mode) for name, mode in modes.items()}
    eligible = [name for name, result in qualifications.items() if result["pass"]]
    strongest = min(eligible, key=lambda name: modes[name]["external_wall_median_ns"]) if eligible else None
    expected_kinds = sorted(["independent_cpp", "independent_cpp", "package_native_vectorized_sklearn"])
    observed_kinds = sorted(mode.get("kind") for mode in modes.values())
    return {
        "schema": "SAC_GEN7_B7_PORTFOLIO_QUALIFICATION_V1",
        "role": "performance_denominator_only",
        "portfolio_complete": len(modes) == 3 and observed_kinds == expected_kinds,
        "mode_qualifications": qualifications,
        "eligible_modes": eligible,
        "strongest_eligible_mode": strongest,
        "pass": bool(strongest)
        and all(result["pass"] for result in qualifications.values())
        and len(modes) == 3
        and observed_kinds == expected_kinds,
    }


def reclassify_record(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    canonical = qualify_canonical_oracle(out)
    b7 = qualify_b7_portfolio(out)
    strongest_name = b7["strongest_eligible_mode"]
    if strongest_name is None:
        raise RuntimeError("no qualified B7 mode")
    modes = out["complete_b7"]
    selected = out.get("selected")
    if selected is not None:
        speed = modes[strongest_name]["external_wall_median_ns"] / selected["external_wall_median_ns"]
        conservative = min(
            modes[name]["external_wall_p05_ns"] for name in b7["eligible_modes"]
        ) / selected["external_wall_p95_ns"]
        out["measured_wall_speedup"] = speed
        out["conservative_p05_over_p95_wall_speedup"] = conservative
    out["canonical_oracle_qualification"] = canonical
    out["b7_portfolio_qualification"] = b7
    out["strongest_b7_mode"] = strongest_name
    out["unit_truth_zero_mismatch"] = canonical["pass"]
    out["diagnostic"] = {
        "package_native_raw_bit_identity_required": False,
        "package_native": {
            name: {
                "raw_bit_mismatches": mode.get("raw_mismatches_max"),
                "max_abs_raw_error": mode.get("max_abs_raw_error"),
            }
            for name, mode in modes.items()
            if mode.get("kind") != "independent_cpp"
        },
    }
    out["pass"] = all(
        [
            out.get("binding", {}).get("pass", True),
            out.get("theory_class", "30X_CERTIFIED") == "30X_CERTIFIED",
            canonical["pass"],
            b7["pass"],
            out.get(
                "canonical_decision_agreement",
                out.get("full_truth_decision")
                == out.get("reported_decision", out.get("full_truth_decision")),
            ),
            out["measured_wall_speedup"] >= 30,
            out["conservative_p05_over_p95_wall_speedup"] >= 10,
        ]
    )
    return out
