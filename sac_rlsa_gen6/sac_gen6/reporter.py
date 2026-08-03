from __future__ import annotations
import argparse,json,platform,sys,time
from pathlib import Path
import numpy as np
from sklearn import datasets
from sklearn.ensemble import GradientBoostingClassifier
from .common import sha256_file,jwrite
from .model_io import export_model

PARAMS=dict(n_estimators=100,min_samples_split=5,max_depth=2,learning_rate=0.1,max_features=2)

def generate(out:Path,target_id:str,seed:int,N:int):
 out.mkdir(parents=True,exist_ok=True);t0=time.perf_counter_ns()
 X,y=datasets.make_hastie_10_2(n_samples=2000+N,random_state=seed)
 clf=GradientBoostingClassifier(**PARAMS,random_state=seed);clf.fit(X[:2000],y[:2000])
 Xt=np.ascontiguousarray(X[2000:],dtype='<f8');yt=np.ascontiguousarray(y[2000:],dtype='<f8')
 raw=np.asarray(clf.decision_function(Xt),dtype='<f8');y01=(yt>0).astype(np.float64)
 loss=np.asarray(np.logaddexp(0.0,raw)-y01*raw,dtype='<f8')
 paths={'x':out/f'{target_id}.X.f64','y':out/f'{target_id}.y.f64','raw':out/f'{target_id}.reported_raw.f64','loss':out/f'{target_id}.reported_loss.f64','model':out/f'{target_id}.model.bin'}
 Xt.tofile(paths['x']);yt.tofile(paths['y']);raw.tofile(paths['raw']);loss.tofile(paths['loss'])
 model=export_model(clf,paths['model'],X[:1]);loss_upper=max(float(np.logaddexp(0.0,model['raw_max'])),float(np.logaddexp(0.0,-model['raw_min'])))
 assert float(loss.max())<=loss_upper+1e-12
 files={k:{'path':p.name,'bytes':p.stat().st_size,'sha256':sha256_file(p)} for k,p in paths.items()}
 rep={'schema':'SAC_GEN6_TARGET_REPORT_V1','target_id':target_id,'seed':seed,'population':N,'training_population':2000,'parameters':PARAMS,'software':{'python':sys.version.split()[0],'numpy':np.__version__,'sklearn':'1.8.0','platform':platform.platform()},'policy':{'metric':'mean Bernoulli log loss from raw logits','formula':'logaddexp(0,raw)-y01*raw','label_mapping':'y01=1 iff make_hastie label >0','probability_clipping':'NONE_AUTHORITATIVE_RAW_LOGIT_PATH','threshold':0.5,'decision':'PASS iff mean_loss < 0.5'},'tree_semantics':{'feature_input_cast':'float32 before each split comparison','comparison':'float32(x_feature) <= stored float64 threshold','leaf_accumulation':'float64 init + learning_rate * leaf values'},'model_bounds':{**model,'loss_upper':loss_upper,'derivation':'max(softplus(raw_max),softplus(-raw_min)) over y01 in {0,1}'},'reported_mean_loss':float(loss.mean()),'reported_min_loss':float(loss.min()),'reported_max_loss':float(loss.max()),'reported_decision':bool(float(loss.mean())<0.5),'files':files,'report_generation_wall_ns':time.perf_counter_ns()-t0,'target_truth_accessed':False}
 rep['report_digest']=__import__('hashlib').sha256(json.dumps(rep,sort_keys=True,separators=(',',':')).encode()).hexdigest();jwrite(out/f'{target_id}.TARGET_REPORT.json',rep);return rep

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--target-id',required=True);ap.add_argument('--seed',type=int,required=True);ap.add_argument('--n',type=int,required=True);a=ap.parse_args();print(json.dumps(generate(Path(a.out),a.target_id,a.seed,a.n),sort_keys=True))
if __name__=='__main__':main()
