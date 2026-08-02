from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from .common import minimal_sample,jwrite,digest

def certify(report_path:Path,cost_path:Path,out:Path,alpha=0.01):
 rep=json.loads(report_path.read_text());cost=json.loads(cost_path.read_text());root=report_path.parent
 loss=np.memmap(root/rep['files']['loss']['path'],dtype='<f8',mode='r',shape=(rep['population'],))
 if not rep['reported_decision']: cls='REPORTED_NEGATIVE_NO_CERTIFICATION';q=0;s=rep['population'];risk=1.0
 else:
  margin_total=(rep['policy']['threshold']-rep['reported_mean_loss'])*rep['population'];caps=np.maximum(0.0,rep['model_bounds']['loss_upper']-np.asarray(loss))
  order=np.sort(caps)[::-1];q=int(np.searchsorted(np.cumsum(order),margin_total,side='left')+1);s,risk=minimal_sample(rep['population'],q,alpha)
  upper=cost['selected_fixed_upper_ns']+cost['selected_per_action_upper_ns']*s;full_lower=cost['full_b7_wall_lower_ns'];pred=full_lower/upper
  cls='30X_CERTIFIED' if pred>=30 else ('10X_CERTIFIED' if pred>=10 else ('3X_CERTIFIED' if pred>=3 else 'UNRESOLVED'))
 cert={'schema':'SAC_GEN6_THEORY_CERTIFICATE_V1','target_id':rep['target_id'],'target_report_digest':rep['report_digest'],'population':rep['population'],'risk_limit':alpha,'reported_decision':rep['reported_decision'],'reported_mean_loss':rep['reported_mean_loss'],'threshold':rep['policy']['threshold'],'loss_upper':rep['model_bounds']['loss_upper'],'q_D_lower_bound':q,'sample_size':s,'hypergeometric_miss_bound':risk,'cost_rule_digest':cost['cost_rule_digest'],'predicted_rlsa_wall_upper_ns':cost['selected_fixed_upper_ns']+cost['selected_per_action_upper_ns']*s,'predicted_b7_wall_lower_ns':cost['full_b7_wall_lower_ns'],'predicted_wall_speedup_lower':cost['full_b7_wall_lower_ns']/(cost['selected_fixed_upper_ns']+cost['selected_per_action_upper_ns']*s),'theory_class':cls,'target_truth_accessed':False,'bad_state_family':'all truth vectors whose total adverse log-loss discrepancy can cross the frozen 0.5 decision threshold under the per-unit model-derived upper bound'}
 cert['freeze_b_sha256']=digest(cert);jwrite(out,cert);return cert

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--report',required=True);ap.add_argument('--cost-rule',required=True);ap.add_argument('--out',required=True);a=ap.parse_args();print(json.dumps(certify(Path(a.report),Path(a.cost_rule),Path(a.out)),sort_keys=True))
if __name__=='__main__':main()
