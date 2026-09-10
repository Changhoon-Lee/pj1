# Public Freeze A — finalized before target execution

This commit finalizes SAC-RLSA Gen6 Freeze A.

```text
GEN5_IMMUTABLE_NEGATIVE_VERDICT = SAC_RLSA_ACTION_SEMANTICS_UNSOUND
GEN5_ZIP_SHA256                 = 7fbc2f675e617b69700ca13fa2dd8e33d44114931be8f1bcd67522b2a3861081
HISTORY_ONLY_SEEDS              = 42, 73
UNTOUCHED_TARGET_SEEDS          = 63, 59
TARGET_REPORTS_PRESENT          = false
TARGET_TRUTH_ACCESSED           = false
FREEZE_A_SHA256                 = f07d44853b78d2583b580442dbccbf61c2640ebf96f0cb5eabe523a605151695
```

The following are fixed before target reporting:

- scikit-learn 1.8.0 source-bound scaled-shadow workflow and the `mean raw-logit Bernoulli log loss < 0.5` decision;
- float32 tree-input comparison semantics and binary64 accumulation;
- exact raw-logit loss with no probability clipping;
- outward-rounded model-derived loss upper bound;
- repaired independent C++ oracle and tolerance;
- history-only cost calibration and strongest-B7 rule;
- 1% risk limit, q_D support model, exact hypergeometric audit;
- untouched target seeds, timing protocol, Ubuntu/macOS same-byte architecture;
- the requirement that Freeze B must be `30X_CERTIFIED` and publicly committed before selected audit or full truth.

No `REPORTER_TRIGGER.json` exists in this commit. Therefore the path-gated workflow cannot generate target reports or access target truth at Freeze A.
