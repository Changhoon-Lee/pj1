# SAC-RLSA Gen5 strongest-B7 repair Freeze A

The original A/B campaign discovered a stronger byte-prefix-LUT B7 after target truth and therefore cannot support the strict prospective claim. This freeze starts untouched C/D partitions with the stronger B7 already fixed.

- Repair Freeze A SHA-256: `5d392ed36e8bf32b874678fe0b00053218dc037a23245e4c04da6dc5dfc346c6`
- Targets C/D: 1,000,000 sequences × 1,024 bits; seeds 202608020501 and 202608020502.
- Policy: the same frozen NIST SP800-22 Rev1a forward Cumulative Sums pass-proportion decision.
- Strongest B7 and sampled actions: the same byte-prefix-LUT C++ evaluator, 4 threads.
- Primary timing: HOT_REUSE, 3 warmups, 21 timed runs; cold one-shot reported separately.
- Development conservative hot speedup lower: 31.746077×.
- No C/D target report, audit randomness, sampled truth, or full truth exists at this commit.
