from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from .common import jwrite,digest

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--freeze-b',required=True);ap.add_argument('--out-json',required=True);ap.add_argument('--out-indices',required=True);ap.add_argument('--salt',required=True);a=ap.parse_args()
 b=json.loads(Path(a.freeze_b).read_text());seed=int.from_bytes(hashlib.sha256((b['freeze_b_sha256']+'|'+a.salt).encode()).digest()[:16],'big')
 rng=np.random.Generator(np.random.PCG64DXSM(seed));idx=np.sort(rng.choice(b['population'],size=b['sample_size'],replace=False).astype('<u4'))
 Path(a.out_indices).parent.mkdir(parents=True,exist_ok=True);idx.tofile(a.out_indices)
 rec={'schema':'SAC_GEN6_FREEZE_C_V1','target_id':b['target_id'],'freeze_b_sha256':b['freeze_b_sha256'],'public_salt':a.salt,'seed_128':seed,'sample_size':len(idx),'indices_sha256':hashlib.sha256(Path(a.out_indices).read_bytes()).hexdigest(),'truth_accessed':False}
 rec['freeze_c_sha256']=digest(rec);jwrite(Path(a.out_json),rec);print(json.dumps(rec,sort_keys=True))
if __name__=='__main__':main()
