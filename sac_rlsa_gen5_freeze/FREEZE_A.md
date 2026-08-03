# SAC-RLSA Gen5 Freeze A

Target truth and target reports do not exist at this freeze.

- Freeze A SHA-256: `fb2ebac92d408ee9ec0ade74e4c0be51e18f8975326820a083dc4ed691d5414c`
- Primary: NIST SP800-22 Rev1a Cumulative Sums pass-proportion, 500,000 sequences, 1,024 bits.
- Target partitions: A seed 202608020101; B seed 202608020202.
- Risk limit: 1%, split equally across lower and upper pass-proportion assertions.
- Strongest B7: compiled independent C++ full audit with identical thread/batching conditions.
- Negative controls: singleton high-influence, NumPy all-mandatory known-answer test, and small-population high-overhead NIST campaign.
- Gen4 verdict is preserved and no target output or target truth exists at this commit.
