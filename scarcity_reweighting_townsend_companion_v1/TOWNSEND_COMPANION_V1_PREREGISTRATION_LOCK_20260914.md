# Townsend Companion v1.0 - external pre-analysis lock

Date: 2026-09-14. Created before Townsend raw microdata access/execution in this project.

This lock applies only to preregistration inputs and executable decision rules. Generated outputs (including `RESULTS/power_design_exact.json`) are deliberately EXCLUDED and are governed by the release seal, not by the preregistration hash set.

This public Git lock is an external timestamped commit. It is NOT represented as an OSF/AEA formal registration.

## Locked scientific hierarchy

- P1 Wilson ordering: diagnostic only.
- D1/P3 slack compression: primary.
- D2 outside-option/obligation pass-through: primary; fail closed if no defensible codebook variable exists.
- P4 crowd-out: formal test only if (i) common cardinal T scale is externally validated and (ii) the preregistered 95% lower confidence bound for net active absorption M_A is > 1.
- P2/P5: secondary.
- Kinnan-style history gate mandatory; hidden-income dominance -> MECHANISM_NOT_IDENTIFIED.
- No d-to-eta conversion before raw-data calibration. No off-grid MDE extrapolation.

## Locked file hashes

- `88750e899f562b35aa05feacee12a32547205663036a4ecfe926910b0e67b927` `EMPIRICS/PREREGISTRATION.md`
- `457275a158f29b79fd08b0888f4a965fcfb9f99316142efcdf6272123c5442d8` `EMPIRICS/MEASUREMENT_BRIDGE.md`
- `4709456fddb25afc15529db693416e0dc0e28a05cf18347bcb6d38a9956959b6` `EMPIRICS/STRUCTURAL_POWER_PROTOCOL.md`
- `e418ff4a890a2ee2ac571240ab05054cbb45f89247d3a83c27920007bffa7fdf` `EMPIRICS/MECHANISM_GATE_TEMPLATE.json`
- `9f1cbdfaa458d82a205789a7c84962773b4f29408175239530b0153c3de0d009` `DATA/VARIABLE_MAP_TEMPLATE.json`
- `5ccc845c29992d2a971c9155aa4cb1efac8334b2f94329136a0d4d33ca3bed27` `CODE/prepare_townsend.py`
- `ab8f10f7ef5f61b0bc16d362c9e4843bca457364c4cc8578ac0d852508cbe395` `CODE/run_preregistered_analysis.py`
- `b975e2aa9e28396db4b3be58204fbe9fed7dcb45ed107858badd1c3e834df14b` `CODE/power_design_exact.py`
- `571584d5710e4b75926d40fb76e80d372161ffb11a2228c7e12e91b35a2a88ad` `PAPER/companion_protocol.tex`

## B1 determinism rule

Reject decisions must be made from exact integer/fixed-point statistics. Floating BLAS/LAPACK may not enter the decision path. Canonical output formatting occurs only after a deterministic reject/non-reject decision is fixed.