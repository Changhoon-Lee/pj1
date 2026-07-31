# CFSC Gen6 external managed-environment reproduction

This branch is an unmerged, reversible reproduction fixture for the CFSC prospective checkability-frontier campaign. It runs 24 lightweight semantic/certificate checks in GitHub-hosted Ubuntu and macOS environments. It does **not** reproduce the local performance ratios and does **not** constitute an independent external research-team audit.

Run locally:

```bash
python -m pip install -r cfsc_gen6_external/requirements.txt
cd cfsc_gen6_external
python reproduce_semantics.py
```

Expected result: `24/24` semantic checks pass and `external_reproduction.json` is emitted.
