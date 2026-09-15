# Phase-II execution mirror — freeze record

This branch is an execution mirror created **after** the local Phase-II scientific freeze and after the outcome-access boundary was crossed. It is not presented as the original freeze timestamp.

Original pre-outcome freeze facts:

- R3 immutable baseline SHA-256: `bb1a735084ff31c8b33460248087c0e30a1d4b583800a840bbaeb83bc9c6b3b4`
- R3 bytes: `55,652,407`
- Phase-II protocol final SHA-256: `8a3fd33cee0f7fefcae911d825a68c3540d4f83dacc6c4030d80e24fb266e43d`
- Frozen analysis script SHA-256: `a946195219bfc17f82bc82be94d8c9d0751c4a59b274b1b18d1e65fa3946ff1c`
- Representation-neutrality characterization SHA-256: `34e7f94857c3b081a4855a97cc5e8abd951381fecb241c6b96b577bcf66b4629`
- Frozen protocol ZIP SHA-256: `9f2497bc603ef6d7e84c77e80e8a2478a5cc9a8e718ea85b04553ae98adb7fe6`
- Local protocol freeze UTC recorded in the frozen protocol: `2026-09-15T06:46:24Z`
- ATLAs language-value outcomes had not been opened, queried, downloaded, parsed, searched, or summarized before the local freeze.
- Outcome access began only after the above hashes existed.

Frozen ATLAs source:

- Zenodo DOI: `10.5281/zenodo.15227808`
- release: `v2025.1`
- archive: `davidainman/atlas-data-v2025.1.zip`
- reported MD5: `c2395e53731144209b809cf077aa8644`
- corresponding Git tag: `v2025.1`
- Git commit: `c01e17ab5fa6c922e79e7415ad65c024d0b386b2`

The five `frozen_script_parts/*.b64` files concatenate to the exact frozen script bytes. The workflow must verify the frozen script SHA before running and the ATLAs archive MD5 before opening the archive.
