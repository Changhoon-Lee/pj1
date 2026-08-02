#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,platform,statistics,subprocess,sys,tempfile,time
from pathlib import Path
import numpy as np

def sha(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def quantized_digest(path:Path,scale:float=1e12)->str:
 x=np.memmap(path,dtype='<f8',mode='r');q=np.rint(np.asarray(x)*scale).astype('<i8');return hashlib.sha256(q.tobytes()).hexdigest()
def invoke(oracle,td,rep,idx,out,threads,truth_out=None):
 args=[str(oracle),'--model',str(td/rep['files']['model']['path']),'--x',str(td/rep['files']['x']['path']),'--y',str(td/rep['files']['y']['path']),'--reported-loss',str(td/rep['files']['loss']['path']),'--reported-raw',str(td/rep['files']['raw']['path']),'--n',str(rep['population']),'--tol','1e-10','--threads',str(threads)]
 if idx is not None:args+=['--indices',str(idx)]
 if truth_out is not None:args+=['--truth-loss-out',str(truth_out)]
 t0=time.perf_counter_ns();cp=subprocess.run(args+['--out',str(out)],check=True,capture_output=True,text=True);external=time.perf_counter_ns()-t0
 rec=json.loads(out.read_text());rec['external_wall_ns']=external;rec['stderr']=cp.stderr[-2000:];return rec
def timed(oracle,td,rep,idx,threads,warmups,runs,work,prefix,truth_once=False):
 for i in range(warmups):invoke(oracle,td,rep,idx,work/f'{prefix}.warm{i}.json',threads)
 rs=[];truth_path=work/f'{prefix}.truth_loss.f64' if truth_once else None
 for i in range(runs):rs.append(invoke(oracle,td,rep,idx,work/f'{prefix}.run{i}.json',threads,truth_path if i==0 else None))
 walls=[r['external_wall_ns'] for r in rs];internal=[r['wall_ns'] for r in rs];cpus=[r['cpu_ns'] for r in rs]
 q=lambda xs,p:float(np.quantile(np.asarray(xs,dtype=float),p,method='linear'))
 return {'runs':runs,'warmups':warmups,'threads':threads,'records':rs,'external_wall_median_ns':float(statistics.median(walls)),'external_wall_p05_ns':q(walls,0.05),'external_wall_p95_ns':q(walls,0.95),'internal_wall_median_ns':float(statistics.median(internal)),'cpu_median_ns':float(statistics.median(cpus)),'raw_mismatches_max':max(r['raw_mismatches'] for r in rs),'loss_mismatches_max':max(r['loss_mismatches'] for r in rs),'decision_agreement_all':all(r['decision']==rep['reported_decision'] for r in rs),'truth_loss_quantized_1e12_sha256':quantized_digest(truth_path) if truth_path else None}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--artifact-root',required=True);ap.add_argument('--freeze-root',required=True);ap.add_argument('--oracle',required=True);ap.add_argument('--out',required=True);ap.add_argument('--warmups',type=int,default=2);ap.add_argument('--runs',type=int,default=11);a=ap.parse_args()
 ar=Path(a.artifact_root);fr=Path(a.freeze_root);oracle=Path(a.oracle).resolve();fa=json.loads((fr/'FREEZE_A_POLICY_ORACLE_COST.json').read_text());res=[]
 with tempfile.TemporaryDirectory() as d:
  work=Path(d)
  for target in fa['untouched_targets']:
   seed=target['seed'];tid=target['target_id'];td=ar/f'seed{seed}';rep=json.loads((td/f'{tid}.TARGET_REPORT.json').read_text());b=json.loads((fr/f'FREEZE_B_SEED{seed}.json').read_text());c=json.loads((fr/f'FREEZE_C_SEED{seed}.json').read_text());idx=fr/f'FREEZE_C_SEED{seed}.indices.u32';assert sha(idx)==c['indices_sha256']
   selected=timed(oracle,td,rep,idx,4,a.warmups,a.runs,work,f'seed{seed}.selected');full1=timed(oracle,td,rep,None,1,a.warmups,a.runs,work,f'seed{seed}.full1',True);full4=timed(oracle,td,rep,None,4,a.warmups,a.runs,work,f'seed{seed}.full4',True)
   modes={'independent_cpp_1thread':full1,'independent_cpp_4thread':full4};best_name=min(modes,key=lambda k:modes[k]['external_wall_median_ns']);best=modes[best_name]
   speed=best['external_wall_median_ns']/selected['external_wall_median_ns'];conservative=min(full1['external_wall_p05_ns'],full4['external_wall_p05_ns'])/selected['external_wall_p95_ns']
   res.append({'target_id':tid,'seed':seed,'report_digest':rep['report_digest'],'freeze_b_sha256':b['freeze_b_sha256'],'freeze_c_sha256':c['freeze_c_sha256'],'theory_class':b['theory_class'],'target_files':{k:v['sha256'] for k,v in rep['files'].items()},'selected':selected,'full_modes':modes,'strongest_b7_mode':best_name,'measured_wall_speedup':speed,'conservative_p05_over_p95_wall_speedup':conservative,'unit_truth_agreement':all(x['loss_mismatches_max']==0 and x['raw_mismatches_max']==0 for x in [selected,full1,full4]),'decision_agreement':all(x['decision_agreement_all'] for x in [selected,full1,full4]),'truth_digest_agreement_between_thread_modes':full1['truth_loss_quantized_1e12_sha256']==full4['truth_loss_quantized_1e12_sha256'],'target_bytes_digest':hashlib.sha256(''.join(v['sha256'] for k,v in sorted(rep['files'].items())).encode()).hexdigest()})
 out={'schema':'SAC_GEN6_CROSS_PLATFORM_PERFORMANCE_RECEIPT_V2','platform':platform.platform(),'machine':platform.machine(),'python':sys.version.split()[0],'oracle_sha256':sha(oracle),'records':res,'all_unit_truth_agree':all(x['unit_truth_agreement'] for x in res),'all_decisions_agree':all(x['decision_agreement'] for x in res),'all_truth_thread_digests_agree':all(x['truth_digest_agreement_between_thread_modes'] for x in res),'all_theory_classes_30x':all(x['theory_class']=='30X_CERTIFIED' for x in res),'all_measured_ge_30x':all(x['measured_wall_speedup']>=30 for x in res),'all_conservative_ge_10x':all(x['conservative_p05_over_p95_wall_speedup']>=10 for x in res)}
 out['pass']=all([out['all_unit_truth_agree'],out['all_decisions_agree'],out['all_truth_thread_digests_agree'],out['all_theory_classes_30x'],out['all_measured_ge_30x'],out['all_conservative_ge_10x']]);Path(a.out).write_text(json.dumps(out,sort_keys=True,indent=2)+'\n');print(json.dumps({'pass':out['pass']},sort_keys=True))
if __name__=='__main__':main()
