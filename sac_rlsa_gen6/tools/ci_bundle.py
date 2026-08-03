#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('cmd');ap.add_argument('--artifact-root',required=True);ap.add_argument('--freeze-root',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();r=Path(a.artifact_root)
 files=[{'path':p.relative_to(r).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(r.rglob('*')) if p.is_file()]
 o={'schema':'SAC_GEN6_CI_ARTIFACT_MANIFEST_V1','files':files,'freeze_b_present':sorted(p.name for p in Path(a.freeze_root).glob('FREEZE_B_*.json')),'freeze_c_present':sorted(p.name for p in Path(a.freeze_root).glob('FREEZE_C_*.json'))}
 Path(a.out).write_text(json.dumps(o,sort_keys=True,indent=2)+'\n')
if __name__=='__main__':main()
