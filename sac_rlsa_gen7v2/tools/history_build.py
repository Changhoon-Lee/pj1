#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, sys, time, resource
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sac_gen7.reporter import generate
from sac_gen7.certify import certify
from sac_gen7.freeze_randomness import freeze
from sac_gen7.common import digest_obj, sha256_file, write_json
from sac_gen7.state_machine import initial_state, transition


def dir_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())


def main() -> None:
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--artifact-root',required=True);p.add_argument('--out',required=True);p.add_argument('--config');a=p.parse_args()
    root=Path(a.root); ar=Path(a.artifact_root); config_path=Path(a.config) if a.config else root/'preflight/HISTORY_DRY_RUN_CONFIG.json'; config=json.loads(config_path.read_text()); fr=ar/'freeze';fr.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/'freeze/FROZEN_COST_RULE.json',fr/'FROZEN_COST_RULE.json')
    records=[];started=time.perf_counter_ns();state0=initial_state('GEN7_V2_HISTORY_DRY_RUN',digest_obj(config),list(config['history_seeds']));write_json(fr/'HISTORY_STATE_0.json',state0)
    for seed,target_id in zip(config['history_seeds'],config['target_ids']):
        if seed in config['target_seeds_forbidden']:raise RuntimeError('prospective target seed forbidden in dry run')
        td=ar/f'seed{seed}'; report,generation=generate(td,target_id,int(seed),int(config['population_each']),'HISTORY_ONLY')
        rp=td/f'{target_id}.SCIENTIFIC_TARGET_REPORT.json';bp=fr/f'FREEZE_B_SEED{seed}.json';cp=fr/f'FREEZE_C_SEED{seed}.json';ip=fr/f'FREEZE_C_SEED{seed}.indices.u32'
        b=certify(rp,fr/'FROZEN_COST_RULE.json',bp,float(config['risk_limit']))
        c=freeze(bp,cp,ip,config['public_salt'])
        records.append({'seed':seed,'target_id':target_id,'report_digest':report['canonical_report_digest'],'report_file_sha256':sha256_file(rp),'freeze_b_sha256':b['freeze_b_sha256'],'freeze_c_sha256':c['freeze_c_sha256'],'indices_sha256':c['indices_sha256'],'theory_class':b['theory_class'],'sample_size':b['sample_size'],'target_truth_accessed':False})
    state1=transition(state0,1,'HISTORY_REPORTS_GENERATED');write_json(fr/'HISTORY_STATE_1.json',state1);state2=transition(state1,2,'HISTORY_FREEZE_B_C_CLOSED');write_json(fr/'HISTORY_STATE_2.json',state2)
    manifest={'schema':'SAC_GEN7_HISTORY_BUILD_MANIFEST_V2','config_digest':digest_obj(config),'records':records,'artifact_bytes':dir_bytes(ar),'generation_wall_ns':time.perf_counter_ns()-started,'peak_rss_native_units':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'target_seeds_used':False,'target_truth_accessed':False}
    manifest['manifest_digest']=digest_obj(manifest);write_json(Path(a.out),manifest);print(json.dumps(manifest,sort_keys=True))
if __name__=='__main__':main()
