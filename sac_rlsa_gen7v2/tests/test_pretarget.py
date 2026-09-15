from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sac_gen7.state_machine import initial_state,transition,verify
from sac_gen7.strict_math import strict_loss_upper
from sac_gen7.reporter import POLICY,TREE_SEMANTICS,CANONICAL_TRUTH

def test_state_machine_sequence():
 s=initial_state('C','a'*64,[1,2]);verify(s)
 for i in range(1,7):s=transition(s,i,f'e{i}');verify(s)
 assert s['state']==6 and s['target_truth_accessed']
def test_state_machine_reject_skip():
 s=initial_state('C','a'*64,[1,2])
 with pytest.raises(RuntimeError):transition(s,2,'bad')
def test_strict_loss_bound_is_outward():assert strict_loss_upper(-10,10)['binary64_strictly_above_reference']
def test_canonical_rules():
 assert POLICY['threshold']==0.5
 assert TREE_SEMANTICS['feature_input_cast'].startswith('IEEE-754 binary32')
 assert CANONICAL_TRUTH['decimal_places']==40
def test_history_forbids_consumed_targets():
 d=json.loads((ROOT/'preflight/HISTORY_DRY_RUN_CONFIG.json').read_text())
 assert set(d['history_seeds']).isdisjoint(d['target_seeds_forbidden']) and d['prospective_target_execution_authorized'] is False
def test_scientific_rule_diff_zero():
 d=json.loads((ROOT/'preflight/SCIENTIFIC_RULE_DIFF.json').read_text())
 assert d['SCIENTIFIC_RULE_DIFF']==0 and not d['target_identity']['pure_transport_supersession_possible']
def test_source_completeness():
 d=json.loads((ROOT/'preflight/SOURCE_COMPLETENESS.json').read_text())
 assert d['pass'] and d['forbidden_transport_artifacts']==[]
def test_consumed_seed_audit():
 d=json.loads((ROOT/'preflight/CONSUMED_TARGETS_AUDIT.json').read_text())
 assert d['consumed_seeds']==[2168,912] and d['prospective_reuse_authorized'] is False
def test_python_canonical_selftest():
 cp=subprocess.run([sys.executable,str(ROOT/'tools/canonical_truth_selftest.py')],capture_output=True,text=True,check=True)
 assert json.loads(cp.stdout)['pass']
