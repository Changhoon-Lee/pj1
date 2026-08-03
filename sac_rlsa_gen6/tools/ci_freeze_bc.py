#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo-root',required=True);ap.add_argument('--artifact-root',required=True);ap.add_argument('--record-root',required=True);ap.add_argument('--freeze-a-commit',required=True);a=ap.parse_args()
 rr=Path(a.repo_root);ar=Path(a.artifact_root);rec=Path(a.record_root);rec.mkdir(parents=True,exist_ok=True);fr=rec/'freeze';tr=rec/'target_reports';fr.mkdir(exist_ok=True);tr.mkdir(exist_ok=True)
 fa=json.loads((rr/'sac_rlsa_gen6/freeze/FREEZE_A_POLICY_ORACLE_COST.json').read_text())
 for n in ['FREEZE_A_POLICY_ORACLE_COST.json','FROZEN_COST_RULE.json','SEED_SELECTION_RULE.json']:(fr/n).write_bytes((rr/'sac_rlsa_gen6/freeze'/n).read_bytes())
 records=[];env={**os.environ,'PYTHONPATH':str(rr/'sac_rlsa_gen6')}
 for t in fa['untouched_targets']:
  seed=t['seed'];tid=t['target_id'];td=ar/f'seed{seed}';td.mkdir(parents=True,exist_ok=True)
  subprocess.run([sys.executable,'-m','sac_gen6.reporter','--out',str(td),'--target-id',tid,'--seed',str(seed),'--n',str(t['population'])],check=True,env=env)
  rp=td/f'{tid}.TARGET_REPORT.json';(tr/f'{tid}.TARGET_REPORT.json').write_bytes(rp.read_bytes())
  bp=fr/f'FREEZE_B_SEED{seed}.json';subprocess.run([sys.executable,'-m','sac_gen6.certify','--report',str(rp),'--cost-rule',str(rr/'sac_rlsa_gen6/freeze/FROZEN_COST_RULE.json'),'--out',str(bp)],check=True,env=env)
  b=json.loads(bp.read_text())
  if b['theory_class']!='30X_CERTIFIED':raise SystemExit(f'seed {seed} did not certify 30X')
  cp=fr/f'FREEZE_C_SEED{seed}.json';ip=fr/f'FREEZE_C_SEED{seed}.indices.u32';salt=a.freeze_a_commit+'|SAC-RLSA-GEN6-FREEZE-C-V2'
  subprocess.run([sys.executable,'-m','sac_gen6.freeze_randomness','--freeze-b',str(bp),'--out-json',str(cp),'--out-indices',str(ip),'--salt',salt],check=True,env=env)
  c=json.loads(cp.read_text());r=json.loads(rp.read_text())
  records.append({'seed':seed,'target_id':tid,'report_digest':r['report_digest'],'target_report_sha256':sha(rp),'freeze_b_sha256':b['freeze_b_sha256'],'freeze_c_sha256':c['freeze_c_sha256'],'indices_sha256':c['indices_sha256'],'theory_class':b['theory_class'],'target_truth_accessed':False})
 trigger={'schema':'SAC_GEN6_FREEZE_BC_PUBLIC_TRIGGER_V1','freeze_a_public_commit':a.freeze_a_commit,'freeze_a_sha256':fa['freeze_a_sha256'],'records':records,'target_truth_accessed':False}
 trigger['freeze_bc_bundle_sha256']=hashlib.sha256(json.dumps(trigger,sort_keys=True,separators=(',',':')).encode()).hexdigest();(fr/'FREEZE_BC_TRIGGER.json').write_text(json.dumps(trigger,sort_keys=True,indent=2)+'\n');print(json.dumps(trigger,sort_keys=True))
if __name__=='__main__':main()
