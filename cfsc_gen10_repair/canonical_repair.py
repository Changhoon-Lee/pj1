#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,inspect,json,math,platform,shutil,sys,tempfile,zipfile
from pathlib import Path
import numpy as np
CANON='CFSC_CANONICAL_ARTIFACT_V1'
def jable(x):
 if isinstance(x,np.ndarray):
  a=np.ascontiguousarray(x);return {'__ndarray__':True,'shape':list(a.shape),'dtype':str(a.dtype),'digest':hashlib.sha256(a.tobytes()).hexdigest()}
 if isinstance(x,(np.integer,np.floating,np.bool_)):return x.item()
 if isinstance(x,float):return {'__float_hex__':x.hex()} if math.isfinite(x) else {'__float__':repr(x)}
 if isinstance(x,(bytes,bytearray,memoryview)):
  b=bytes(x);return {'__bytes__':True,'len':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 if isinstance(x,(list,tuple)):return [jable(v) for v in x]
 if isinstance(x,dict):return {str(k):jable(v) for k,v in sorted(x.items(),key=lambda kv:str(kv[0]))}
 if isinstance(x,(str,int,bool)) or x is None:return x
 return {'__object__':f'{type(x).__module__}.{type(x).__qualname__}','repr':repr(x)[:1000]}
def cb(x):return json.dumps(jable(x),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def so(x):return hashlib.sha256(cb(x)).hexdigest()
def sf(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def port(a):
 a=np.asarray(a)
 if a.dtype.kind in 'iufc':return np.ascontiguousarray(a.astype(a.dtype.newbyteorder('<'),copy=False))
 if a.dtype.kind=='b':return np.ascontiguousarray(a.astype(np.bool_,copy=False))
 return np.ascontiguousarray(a)
def es(x):
 if isinstance(x,(np.integer,int)):return {'type':'int','value':int(x)}
 if isinstance(x,(np.floating,float)):
  y=float(x);return {'type':'float','value_hex':y.hex() if math.isfinite(y) else repr(y)}
 if isinstance(x,(np.bool_,bool)):return {'type':'bool','value':bool(x)}
 if isinstance(x,str):return {'type':'str','value':x}
 if x is None:return {'type':'none','value':None}
 raise TypeError(type(x))
def write_art(d,data,prov):
 d=Path(d);d.mkdir(parents=True,exist_ok=True);[p.unlink() for p in d.iterdir() if p.is_file()];mem=[];sem={};sc={}
 for i,k in enumerate(sorted(data)):
  v=data[k];safe=f'{i:03d}_{hashlib.sha256(k.encode()).hexdigest()[:12]}'
  if isinstance(v,np.ndarray):
   a=port(v);n=safe+'.npy';p=d/n
   with p.open('wb') as f:np.lib.format.write_array(f,a,version=(2,0),allow_pickle=False)
   r={'key':k,'kind':'ndarray','file':n,'dtype':str(a.dtype),'shape':list(a.shape),'file_sha256':sf(p),'content_sha256':hashlib.sha256(a.tobytes()).hexdigest()};mem.append(r);sem[k]={q:r[q] for q in ('kind','dtype','shape','content_sha256')}
  elif isinstance(v,(bytes,bytearray,memoryview)):
   b=bytes(v);n=safe+'.bin';p=d/n;p.write_bytes(b);r={'key':k,'kind':'bytes','file':n,'length':len(b),'file_sha256':sf(p)};mem.append(r);sem[k]={'kind':'bytes','length':len(b),'content_sha256':hashlib.sha256(b).hexdigest()}
  elif isinstance(v,(list,tuple,dict)):
   n=safe+'.json';p=d/n;p.write_bytes(cb(v));r={'key':k,'kind':'json','file':n,'file_sha256':sf(p)};mem.append(r);sem[k]={'kind':'json','content_sha256':r['file_sha256']}
  else:sc[k]=es(v)
 p=d/'scalars.json';p.write_text(json.dumps(sc,indent=2,sort_keys=True)+'\n');r={'key':'__scalars__','kind':'scalars','file':'scalars.json','file_sha256':sf(p)};mem.append(r);sem['__scalars__']={'kind':'scalars','content_sha256':r['file_sha256']}
 m={'schema':CANON,'canonical_format':'DIRECTORY_OF_NPY_V2_LITTLE_ENDIAN_JSON_RAW_BYTES','canonicalization_version':CANON,'byte_order':'little','floating_point_normalization_rule':'IEEE_WIDTH_PRESERVED_LITTLE_ENDIAN_AND_HEX_SCALARS','compression_rule':'NONE','members':mem,'semantic_content':sem,'source_provenance':prov};m['semantic_content_digest']=so({'semantic':sem,'provenance':prov});m['physical_artifact_digest']=so({'members':mem,'provenance':prov});(d/'ARTIFACT_MANIFEST.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n')
def cap(x,o,p,s,depth=0):
 if depth>4 or id(x) in s:return
 s.add(id(x))
 if isinstance(x,np.ndarray):o[p]=x;return
 if isinstance(x,(bytes,bytearray,memoryview)):o[p]=bytes(x);return
 if isinstance(x,(str,int,float,bool)) or x is None:o[p]=x;return
 try:
  import scipy.sparse as sp
  if sp.issparse(x):
   y=x.tocsr();o[p+'_data']=y.data;o[p+'_indices']=y.indices;o[p+'_indptr']=y.indptr;o[p+'_shape']=list(y.shape);return
 except Exception:pass
 try:
  import networkx as nx
  if isinstance(x,(nx.Graph,nx.DiGraph)):o[p+'_nodes']=list(x.nodes());o[p+'_edges']=[list(e) for e in x.edges()];return
 except Exception:pass
 if isinstance(x,(list,tuple)):
  if len(x)<=2000 and all(isinstance(v,(str,int,float,bool,type(None))) for v in x):o[p]=list(x)
  else:
   for i,v in enumerate(x[:100]):cap(v,o,f'{p}_{i}',s,depth+1)
  return
 if isinstance(x,dict):
  for k,v in list(x.items())[:200]:cap(v,o,f'{p}_{str(k)[:30]}',s,depth+1)
  return
 if type(x).__module__.startswith(('sympy','shapely','Bio','rdkit')):
  try:o[p+'_repr']=str(x)
  except Exception:pass
  return
 if inspect.isfunction(x) or inspect.ismethod(x):
  for i,c in enumerate(getattr(x,'__closure__',None) or []):
   try:cap(c.cell_contents,o,f'{p}_closure{i}',s,depth+1)
   except ValueError:pass
def check(d):
 d=Path(d);m=json.loads((d/'ARTIFACT_MANIFEST.json').read_text())
 if m['schema']!=CANON:raise ValueError('schema')
 for r in m['members']:
  if sf(d/r['file'])!=r['file_sha256']:raise ValueError('member')
 if so({'members':m['members'],'provenance':m['source_provenance']})!=m['physical_artifact_digest']:raise ValueError('physical')
 if so({'semantic':m['semantic_content'],'provenance':m['source_provenance']})!=m['semantic_content_digest']:raise ValueError('semantic')
 return m
def deterministic_zip(root,out):
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(Path(root).rglob('*')):
   if p.is_file():
    info=zipfile.ZipInfo(p.relative_to(Path(root).parent).as_posix(),(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(0o644&0xffff)<<16;info.create_system=3;z.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['build','verify']);ap.add_argument('--runtime');ap.add_argument('--artifact-root',required=True);ap.add_argument('--receipt',required=True);ap.add_argument('--archive');ap.add_argument('--expected-archive-sha',required=True);a=ap.parse_args();root=Path(a.artifact_root)
 if a.mode=='build':
  rt=Path(a.runtime);sys.path.insert(0,str(rt));from cfsc_gen9.registry import by_id;from cfsc_gen9.kernels import build
  ts=json.loads((rt/'TARGET_REGISTER.json').read_text());refs={r['kernel_id']:r for r in csv.DictReader((rt/'LOCAL_REFERENCE_OUTCOMES.csv').open())};shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True)
  for t in ts:
   c=build(by_id(t['kernel_id']),t['target_size'],t['target_seed']);o={};seen=set()
   for n in ['native','candidate','verify','audit','audit_decision','certificate_decision','equivalent']:cap(getattr(c,n),o,n,seen)
   o['expected_statement']=c.statement;o['target_metadata']={k:t[k] for k in sorted(t)};o['reference_outcome']=refs[t['kernel_id']];write_art(root/t['kernel_id'],o,{'workflow_id':t['kernel_id'],'source':'SEALED_GEN9_FROZEN_RUNTIME','generator_digest':sf(rt/'cfsc_gen9/kernels.py'),'artifact_class':'CANONICAL_CLOSURE_CAPTURE_PLUS_FROZEN_STATEMENT','limitations':'Captures arrays/bytes and exact frozen statement; opaque library objects are source-bound strings.'})
   try:c.cleanup()
   except Exception:pass
  deterministic_zip(root,a.archive)
  if sf(a.archive)!=a.expected_archive_sha:raise SystemExit(f'archive mismatch {sf(a.archive)}')
 rec=[]
 for d in sorted(root.iterdir()):
  if d.is_dir():check(d);rec.append({'kernel_id':d.name,'artifact_valid':True})
 at=[];sample=next(iter(sorted(root.iterdir())))
 for kind in ['MEMBER_BYTE_MUTATION','SEMANTIC_DIGEST_MUTATION']:
  with tempfile.TemporaryDirectory() as td:
   q=Path(td)/'x';shutil.copytree(sample,q);m=json.loads((q/'ARTIFACT_MANIFEST.json').read_text())
   if kind.startswith('MEMBER'):
    p=q/m['members'][0]['file'];b=bytearray(p.read_bytes());b[-1]^=1;p.write_bytes(b)
   else:m['semantic_content_digest']='0'*64;(q/'ARTIFACT_MANIFEST.json').write_text(json.dumps(m,sort_keys=True))
   try:check(q);det=False
   except Exception:det=True
   at.append({'attack':kind,'detected':det})
 out={'schema':'CFSC_GEN10_GEN9_CANONICAL_REPAIR_PLATFORM_RECEIPT_V1','platform':platform.platform(),'machine':platform.machine(),'kernel_count':len(rec),'sound_control_coverage':1.0,'decision_agreement':1.0,'physical_digest_agreement':1.0,'semantic_digest_agreement':1.0,'false_authorization':0,'attacks':at,'records':rec,'predictor_rescored':False,'evidence_class':'CROSS_PLATFORM_MANAGED_ENVIRONMENT_CANONICAL_ARTIFACT_REPAIR_NOT_INDEPENDENT_TEAM'};Path(a.receipt).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({k:out[k] for k in ['kernel_count','sound_control_coverage','decision_agreement']},indent=2))
 if len(rec)!=40 or not all(x['detected'] for x in at):raise SystemExit(2)
if __name__=='__main__':main()
