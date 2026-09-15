#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:?output executable required}"
RECEIPT="${2:-${OUT}.build.json}"
CXX="${CXX:-c++}"
FLAGS=(-x c++ -O3 -std=c++20 -pthread -fno-fast-math -ffp-contract=off)
mkdir -p "$(dirname "$OUT")" "$(dirname "$RECEIPT")"
"$CXX" "${FLAGS[@]}" "$ROOT/native/gb_oracle.cpp" -o "$OUT"
SELFTEST="$($OUT --self-test)"
python - "$ROOT/native/gb_oracle.cpp" "$OUT" "$RECEIPT" "$CXX" "$SELFTEST" "${FLAGS[*]}" <<'PY'
import hashlib,json,subprocess,sys
from pathlib import Path
source,binary,receipt,cxx,selftest,flags=map(str,sys.argv[1:])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
version=subprocess.run([cxx,'--version'],capture_output=True,text=True,check=True).stdout.splitlines()[0]
st=json.loads(selftest)
obj={'schema':'SAC_GEN7_ORACLE_BUILD_RECEIPT_V2','source_sha256':sha(source),'binary_sha256':sha(binary),'compiler':cxx,'compiler_version':version,'flags':flags.split(),'required_flags_present':all(x in flags.split() for x in ['-fno-fast-math','-ffp-contract=off','-std=c++20']),'self_test':st,'pass':bool(st.get('pass')) and all(x in flags.split() for x in ['-fno-fast-math','-ffp-contract=off','-std=c++20'])}
Path(receipt).write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')
if not obj['pass']:raise SystemExit(2)
PY
