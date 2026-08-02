#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; OUT="$1"; CXX="${CXX:-c++}"
mkdir -p "$(dirname "$OUT")"
"$CXX" -O3 -std=c++20 -pthread "$ROOT/native/gb_oracle.cpp" -o "$OUT"
