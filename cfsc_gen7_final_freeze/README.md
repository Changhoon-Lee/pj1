# CFSC Gen7 final predictor freeze

This directory publicly commits the final pre-execution predictor before any blind holdout target-size run.

Scope:
- completely new corpus relative to the prior Gen6 project/function pairs;
- 12 development kernels and 20 blind holdout kernels;
- primary endpoint: wall-clock producer overhead and independent-validation advantage;
- producer threshold: calibrated rho <= 2.0;
- validation threshold: calibrated advantage >= 10.0;
- target sizes, target seeds, preflight receipt hashes, prediction labels, calibration constants, and code hashes are committed by `FREEZE_COMMITMENT.json` and by the full local freeze digest;
- no target-size holdout result existed when this commit was created.

This commitment is not a scientific-result claim and not a Nature-readiness claim. The complete canonical `PREDICTION_FREEZE.json` will be included in the sealed campaign package and must hash to the committed digest.
