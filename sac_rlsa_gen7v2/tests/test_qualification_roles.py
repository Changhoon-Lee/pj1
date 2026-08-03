from __future__ import annotations

from sac_gen7.qualification_roles import qualify_b7_mode, qualify_canonical_oracle


def test_package_native_raw_bits_are_diagnostic_only():
    mode = {
        "kind": "package_native_vectorized_sklearn",
        "loss_interval_mismatches_max": 0,
        "loss_bound_violations_max": 0,
        "native_decision_all": True,
        "raw_mismatches_max": 100,
        "max_abs_raw_error": 1e-15,
        "max_abs_loss_error": 1e-15,
    }
    result = qualify_b7_mode("sklearn", mode)
    assert result["pass"]
    assert result["raw_bit_mismatches_diagnostic"] == 100
    assert result["equivalence_class"] == "FROZEN_TOLERANCE_AND_DECISION_EQUIVALENT"


def test_strict_cpp_still_requires_exact_raw():
    mode = {
        "kind": "independent_cpp",
        "loss_interval_mismatches_max": 0,
        "loss_bound_violations_max": 0,
        "native_decision_all": True,
        "raw_mismatches_max": 1,
        "max_abs_raw_error": 1e-15,
        "max_abs_loss_error": 1e-15,
    }
    assert not qualify_b7_mode("cpp", mode)["pass"]


def test_canonical_oracle_ignores_package_native_mode():
    strict = {
        "kind": "independent_cpp",
        "truth_raw_sha256": "a" * 64,
        "raw_mismatches_max": 0,
        "loss_interval_mismatches_max": 0,
        "loss_bound_violations_max": 0,
        "native_decision_all": True,
    }
    record = {
        "complete_b7": {
            "cpp1": dict(strict),
            "cpp4": dict(strict),
            "sklearn": {
                "kind": "package_native_vectorized_sklearn",
                "raw_mismatches_max": 999,
            },
        },
        "canonical_truth": {"reported_loss_mismatches": 0},
        "canonical_decision_agreement": True,
    }
    assert qualify_canonical_oracle(record)["pass"]
