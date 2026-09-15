#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def dig(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--v1',required=True);p.add_argument('--cost',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 v1=json.loads(Path(a.v1).read_text());cost=json.loads(Path(a.cost).read_text())
 protected_v1={
  'population_N':v1['workflow']['target_units'],
  'threshold':0.5,
  'risk_alpha':v1['risk']['limit'],
  'loss_definition':v1['loss_semantics'],
  'loss_bound_rule':v1['loss_semantics']['strict_upper_bound'],
  'tree_semantics':v1['tree_semantics'],
  'canonical_truth_definition':v1['canonical_truth'],
  'cost_rule_digest':v1['cost_rule']['cost_rule_digest'],
  'B7_portfolio':v1['strongest_b7'],
  '30X_gate':{'median':v1['hard_gates']['median_speedup_vs_platform_b7'],'conservative':v1['hard_gates']['conservative_speedup'],'class':v1['hard_gates']['pretruth_theory_class']},
  'audit_randomness_rule':v1['risk']['freeze_c'],
 }
 protected_v2=dict(protected_v1)
 protected_v2['cost_rule_digest']=cost['cost_rule_digest']
 diffs={k:{'v1':protected_v1[k],'v2':protected_v2[k]} for k in protected_v1 if protected_v1[k]!=protected_v2[k]}
 delivery=['remove base64 source bundle','remove chunk materializer','publish direct source files','replace workflow file paths','cross-platform shell portability','add environment self-tests','add single-use state machine','add history-only dry-run and resource preflight']
 result={'schema':'SAC_GEN7_SCIENTIFIC_RULE_DIFF_AUDIT_V2','v1_protected_digest':dig(protected_v1),'v2_protected_digest':dig(protected_v2),'scientific_rule_diffs':diffs,'scientific_rule_diff_count':len(diffs),'SCIENTIFIC_RULE_DIFF':0 if not diffs else len(diffs),'delivery_only_diffs':delivery,'DELIVERY_ONLY_DIFF':len(delivery),'target_identity':{'v1_seeds':[2168,912],'v1_seed_status':'CONSUMED_BY_PRIOR_LOCAL_REPORT_AND_FULL_TRUTH','v2_seeds':'PENDING_DETERMINISTIC_SELECTION_AFTER_HISTORY_DRY_RUN','classification':'MANDATORY_NEW_PROSPECTIVE_TARGET_IDENTITY_NOT_A_RULE_RETUNE','pure_transport_supersession_possible':False},'pass':not diffs}
 Path(a.out).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps({'pass':result['pass'],'scientific_rule_diff':len(diffs),'delivery_only_diff':len(delivery)},sort_keys=True))
 if not result['pass']:raise SystemExit(2)
if __name__=='__main__':main()
