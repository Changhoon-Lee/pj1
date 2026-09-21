#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
import tempfile
from pathlib import Path

source = Path(__file__).with_name("build_split_handoff.py")
text = source.read_text(encoding="utf-8")
old = "piece_size = 60 * 1024 * 1024"
new = "piece_size = 70 * 1024 * 1024"
if text.count(old) != 1:
    raise SystemExit("expected exactly one target piece-size definition")
patched = text.replace(old, new)
with tempfile.TemporaryDirectory() as td:
    target = Path(td) / "build_split_handoff_patched.py"
    target.write_text(patched, encoding="utf-8")
    sys.argv[0] = str(target)
    runpy.run_path(str(target), run_name="__main__")
