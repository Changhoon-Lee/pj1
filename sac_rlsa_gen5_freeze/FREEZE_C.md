# SAC-RLSA Gen5 Freeze C

Public audit randomness is derived after Freeze B and before target truth.

- Freeze C SHA-256: `ca99c281348727ccc1a571f364b5d752a43552e2cb700924b94df004f32c80d5`
- Base randomness digest: `f3c88b4ab2f1fd7c170f3bb17e11f011d78d018b0afd0ed191bffa8bbbf959f9`
- Partition A seed: `2965243554482064806`
- Partition B seed: `12888239158928363219`
- Randomness derivation: SHA256(domain || public Freeze-B commit SHA || Freeze-B digest), followed by a partition-specific SHA256.
- Target B10 truth has not been accessed at this commit.
