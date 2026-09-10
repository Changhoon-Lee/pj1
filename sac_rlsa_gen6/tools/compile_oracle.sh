#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; OUT="$1"; CXX="${CXX:-c++}"
mkdir -p "$(dirname "$OUT")"
SRC="$(mktemp -t sac_gen6_oracle_XXXXXX.cpp)"
trap 'rm -f "$SRC"' EXIT
python - "$ROOT/native/gb_oracle.cpp.b64" "$SRC" <<'PY'
import base64,sys
open(sys.argv[2],'wb').write(base64.b64decode(open(sys.argv[1],'rb').read(),validate=True))
PY
ACTUAL=$(python - "$SRC" <<'PY'
import hashlib,sys
print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())
PY
)
EXPECTED=8c743aa15685f18bf70830c78a3ce61580734d7144ac0039cd5681814bf2e46a
[ "$ACTUAL" = "$EXPECTED" ] || { echo "oracle source digest mismatch: $ACTUAL" >&2; exit 2; }
"$CXX" -x c++ -O3 -std=c++20 -pthread "$SRC" -o "$OUT"
