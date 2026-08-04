#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True);a=p.parse_args();root=Path(a.root)
 required=['sac_gen7/common.py','sac_gen7/model_io.py','sac_gen7/reporter.py','sac_gen7/certify.py','sac_gen7/freeze_randomness.py','sac_gen7/strict_math.py','sac_gen7/state_machine.py','native/gb_oracle.cpp','tools/compile_oracle.sh','tools/canonical_truth.py','tools/canonical_truth_selftest.py','tools/sklearn_b7.py','tools/history_build.py','tools/history_platform_run.py','tools/history_aggregate.py','tools/target_generate.py','tools/target_freeze_bc.py','tools/target_selected_platform.py','tools/target_selected_aggregate.py','tools/target_full_platform.py','tools/target_full_aggregate.py','.github/workflows/gen7-history-dry-run.yml','.github/workflows/gen7-target-single-use.yml']
 files={x:{'exists':(root/x).is_file(),'sha256':sha(root/x) if (root/x).is_file() else None,'bytes':(root/x).stat().st_size if (root/x).is_file() else None} for x in required}
 forbidden=[]
 for q in root.rglob('*'):
  if q.is_file() and (q.suffix=='.b64' or 'source_bundle' in q.name or 'materializer' in q.name.lower() or 'source_chunks' in q.parts):forbidden.append(str(q.relative_to(root)))
 result={'schema':'SAC_GEN7_DIRECT_SOURCE_COMPLETENESS_V2','required_files':files,'forbidden_transport_artifacts':forbidden,'base64_bundle_removed':not forbidden,'all_required_direct_sources_present':all(v['exists'] for v in files.values()),'pass':all(v['exists'] for v in files.values()) and not forbidden}
 Path(a.out).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
 print(json.dumps({'pass':result['pass'],'required':len(files),'forbidden':forbidden},sort_keys=True))
 if not result['pass']:raise SystemExit(2)
if __name__=='__main__':main()
