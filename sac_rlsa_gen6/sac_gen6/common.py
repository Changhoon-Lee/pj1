from __future__ import annotations
import hashlib,json,math
from pathlib import Path

def sha256_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def canonical(obj)->bytes:return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(obj)->str:return hashlib.sha256(canonical(obj)).hexdigest()
def jwrite(p:Path,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
def log_hypergeom_miss(N:int,q:int,s:int)->float:
 if s<0 or s>N:return float('-inf')
 if q<=0:return 0.0
 if s>N-q:return float('-inf')
 return math.lgamma(N-q+1)-math.lgamma(s+1)-math.lgamma(N-q-s+1)-math.lgamma(N+1)+math.lgamma(s+1)+math.lgamma(N-s+1)
def minimal_sample(N:int,q:int,alpha:float)->tuple[int,float]:
 lo,hi=0,N;la=math.log(alpha)
 while lo<hi:
  m=(lo+hi)//2
  if log_hypergeom_miss(N,q,m)<=la:hi=m
  else:lo=m+1
 s=lo;return s,0.0 if s>N-q else math.exp(log_hypergeom_miss(N,q,s))
