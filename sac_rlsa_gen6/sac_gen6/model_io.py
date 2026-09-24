from __future__ import annotations
import math,struct,numpy as np
from pathlib import Path

def dn(x):return math.nextafter(float(x),-math.inf)
def up(x):return math.nextafter(float(x),math.inf)
def raw_bounds(clf,X_probe):
 init=float(clf._raw_predict_init(np.asarray(X_probe[:1],dtype=np.float32))[0,0]);lo=dn(init);hi=up(init);lr=float(clf.learning_rate)
 for est in clf.estimators_.ravel():
  tr=est.tree_;v=tr.value[tr.children_left==-1,0,0].astype(float);lo=dn(lo+dn(lr*float(v.min())));hi=up(hi+up(lr*float(v.max())))
 return init,lo,hi

def export_model(clf,path:Path,X_probe):
 init,rmin,rmax=raw_bounds(clf,X_probe);trees=list(clf.estimators_.ravel())
 with path.open('wb') as f:
  f.write(b'SACGBM1\0');f.write(struct.pack('<IIII',1,int(clf.n_features_in_),len(trees),0));f.write(struct.pack('<ddddd',float(clf.learning_rate),init,rmin,rmax,0.0))
  for est in trees:
   tr=est.tree_;f.write(struct.pack('<II',tr.node_count,int(tr.max_depth)))
   for i in range(tr.node_count):
    f.write(struct.pack('<iii',int(tr.children_left[i]),int(tr.children_right[i]),int(tr.feature[i])));f.write(struct.pack('<ddd',float(tr.threshold[i]),float(tr.value[i,0,0]),float(tr.weighted_n_node_samples[i])))
 return {'init_raw':init,'raw_min':rmin,'raw_max':rmax,'n_features':int(clf.n_features_in_),'n_trees':len(trees),'rounding':'outward_nextafter_each_tree_term_and_sum'}
