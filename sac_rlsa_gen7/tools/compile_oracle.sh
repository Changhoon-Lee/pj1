#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:?output executable required}"
CXX="${CXX:-c++}"
EXPECTED="0d4bc494860b9f56326fa35f74fb0a1bd4151d8f1de8b25256744e620152295d"
ACTUAL=$(python - "$ROOT/native/gb_oracle.cpp" <<'PY'
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
)
[ "$ACTUAL" = "$EXPECTED" ] || { echo "oracle source digest mismatch: $ACTUAL" >&2; exit 2; }
mkdir -p "$(dirname "$OUT")"
"$CXX" -x c++ -O3 -std=c++20 -pthread -fno-fast-math -ffp-contract=off "$ROOT/native/gb_oracle.cpp" -o "$OUT"
