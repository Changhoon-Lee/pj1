# CFSC-SVR Gen9 public pre-target freeze

This commit is a public timestamped commitment created before any target-size execution.

* Rule SHA-256: `1c3e406bd2cabc730868929d01d5a72fb954c4070d005e63c3898e3b8003ac5d`
* Full local freeze SHA-256: `a34f2d2d107076168dfff895ffb79aafff75448b100d2d84062323b83378a9fd`
* Raw probe receipts SHA-256: `f84743d4ccf134baeb235c4174b3b4033bf26f86e0ba4ece6b50b59f687adccc`
* Corpus register SHA-256: `6a0de3831edab3320c5f29ae43b5870bbf63e1afaa60ecf65e00bb60e0e46ee8`
* Workflow freeze SHA-256: `5d8c110172eac07e3778f37127546223ffcd3125eb6ebc72c6ea38e54bb18738`
* Primary holdout: 32
* Frozen reserve: 8
* Target results present at freeze: **false**

The primary rule is byte-exactly extracted from sealed Gen8: `PASS iff largest-probe audit/verifier wall-clock ratio >= 10`. There is no retuning and no ABSTAIN. The local package contains full raw probe receipts; this public commit records their digest and the complete per-kernel probe ratio, prediction, target size, target seed, and expected-statement digest.

Frozen gates: coverage 100%; balanced accuracy, sensitivity, and specificity each at least 85%; standard FPR at most 10%; exact 95% accuracy lower bound at least 65%; exact 95% specificity lower bound at least 60%.

This commitment is not a target result, external-team reproduction, lifecycle claim, or Nature-readiness claim.
