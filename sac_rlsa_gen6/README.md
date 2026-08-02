# SAC-RLSA Gen6 — Public Freeze A

This branch records the **pre-target** policy, repaired oracle semantics, cost rule, untouched seeds, timing protocol, and cross-platform execution plan for `SAC_RLSA_REPAIRED_ORACLE_PROSPECTIVE_CONFIRMATION_GEN6`.

At this Freeze A state:

- Gen5 remains `SAC_RLSA_ACTION_SEMANTICS_UNSOUND`; its Seed 42 failure is preserved.
- Seeds 42 and 73 are calibration/history only and receive no prospective credit.
- New untouched seeds are 63 and 59.
- No target report or target truth has been generated or accessed.
- Tree traversal uses `float32(x_feature) <= stored float64 threshold` with binary64 accumulation.
- Bernoulli log loss is evaluated from raw logits as `logaddexp(0, raw) - y01*raw`; probability clipping is forbidden.
- The loss upper bound is derived from an outward-rounded model raw-score interval.
- Full truth may begin only after target reports and `30X_CERTIFIED` Freeze B/C records are publicly committed.

The workflow in this branch is path-gated: merely publishing Freeze A does not execute any target. A later `freeze/REPORTER_TRIGGER.json` commit starts report generation, commits Freeze B/C before truth, then runs the same target bytes on Ubuntu x86_64 and macOS arm64.
