# Implementation Amendment A1 — protocol-fidelity output completion

Recorded before viewing the Phase-II run summary or any outcome-bearing result artifact.

## Frozen material unchanged
- Protocol SHA-256: `8a3fd33cee0f7fefcae911d825a68c3540d4f83dacc6c4030d80e24fb266e43d`
- Original frozen script SHA-256: `a946195219bfc17f82bc82be94d8c9d0751c4a59b274b1b18d1e65fa3946ff1c`
- ATLAs release, metrics, selectors, thresholds, eps, representations, claim map: unchanged.

## Implementation omission found
The original frozen script computes the exact mechanism identity and aggregate reversal-conditioned mechanism summaries, but it does not emit:
1. an auditable per-strict-reversal mechanism record for every primary reversal, despite Protocol §7 stating “For every strict reversal, record …”; and
2. all-eligible shift/contribution distributions in the zero-reversal case, despite Protocol §11.6 requiring these even when reversal-conditioned outputs are empty.

This omission does not change the primary/strict triplet estimands, nearest-set estimands, or governance labels. It affects only completeness of the mechanism deliverable.

## Allowed repair
Under Protocol §11.3, create an implementation-only amended script that:
- preserves every scientific rule and all existing output calculations;
- additionally streams one record per primary strict reversal with anchor/candidate IDs, Domain margin, FeatureSet margin, Delta, overshoot, top driver, top1/top3 absolute-contribution shares;
- additionally accumulates all-primary-eligible Delta / abs(Delta) distributions and per-FeatureSet signed/absolute contributions, so the mechanism remains reportable even if there are zero reversals;
- reasserts `Delta = sum_s c_s` at `<=1e-10`;
- cannot alter eligibility, distance metrics, representations, sign epsilon, or outcome labels.

The original one-shot run remains canonical for the frozen primary/strict outcome. The amended rerun is canonical only for completion/verification of mechanism outputs, unless byte/numeric identity of overlapping outputs is demonstrated.

Local pre-result note SHA-256: `17a25ff32f8c72bdc0113be6aa827b270380ae4fea6d4b6cd3eb73a9e97dfb41`.
