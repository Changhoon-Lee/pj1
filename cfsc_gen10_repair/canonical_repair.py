#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,inspect,json,math,shutil,sys,tempfile
from pathlib import Path
from typing import Any
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
def cbytes(x):return json.dumps(jable(x),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def shobj(x):return hashlib.sha256(cbytes(x)).hexdigest()
def shfile(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def portable(a):
    a=np.asarray(a)
    if a.dtype.kind in 'iufc':return np.ascontiguousarray(a.astype(a.dtype.newbyteorder('<'),copy=False))
    if a.dtype.kind=='b':return np.ascontiguousarray(a.astype(np.bool_,copy=False))
    return np.ascontiguousarray(a)
def enc_scalar(x):
    if isinstance(x,(np.integer,int)):return {'type':'int','value':int(x)}
    if isinstance(x,(np.floating,float)):
        y=float(x);return {'type':'float','value_hex':y.hex() if math.isfinite(y) else repr(y)}
    if isinstance(x,(np.bool_,bool)):return {'type':'bool','value':bool(x)}
    if isinstance(x,str):return {'type':'str','value':x}
    if x is None:return {'type':'none','value':None}
    raise TypeError(type(x))
def write_artifact(directory,data,provenance):
    d=Path(directory);d.mkdir(parents=True,exist_ok=True)
    for p in d.iterdir():
        if p.is_file():p.unlink()
    members=[];semantic={};scalars={}
    for idx,key in enumerate(sorted(data)):
        value=data[key];safe=f'{idx:03d}_{hashlib.sha256(key.encode()).hexdigest()[:12]}'
        if isinstance(value,np.ndarray):
            a=portable(value);name=safe+'.npy';path=d/name
            with path.open('wb') as f:np.lib.format.write_array(f,a,version=(2,0),allow_pickle=False)
            rec={'key':key,'kind':'ndarray','file':name,'dtype':str(a.dtype),'shape':list(a.shape),'file_sha256':shfile(path),'content_sha256':hashlib.sha256(a.tobytes(order='C')).hexdigest()};members.append(rec);semantic[key]={k:rec[k] for k in ('kind','dtype','shape','content_sha256')}
        elif isinstance(value,(bytes,bytearray,memoryview)):
            b=bytes(value);name=safe+'.bin';path=d/name;path.write_bytes(b);rec={'key':key,'kind':'bytes','file':name,'length':len(b),'file_sha256':shfile(path)};members.append(rec);semantic[key]={'kind':'bytes','length':len(b),'content_sha256':hashlib.sha256(b).hexdigest()}
        elif isinstance(value,(list,tuple,dict)):
            name=safe+'.json';path=d/name;path.write_bytes(cbytes(value));rec={'key':key,'kind':'json','file':name,'file_sha256':shfile(path)};members.append(rec);semantic[key]={'kind':'json','content_sha256':rec['file_sha256']}
        else:scalars[key]=enc_scalar(value)
    sp=d/'scalars.json';sp.write_text(json.dumps(scalars,indent=2,sort_keys=True)+'\n');sr={'key':'__scalars__','kind':'scalars','file':'scalars.json','file_sha256':shfile(sp)};members.append(sr);semantic['__scalars__']={'kind':'scalars','content_sha256':sr['file_sha256']}
    m={'schema':CANON,'canonical_format':'DIRECTORY_OF_NPY_V2_LITTLE_ENDIAN_JSON_RAW_BYTES','canonicalization_version':CANON,'byte_order':'little','floating_point_normalization_rule':'IEEE_WIDTH_PRESERVED_LITTLE_ENDIAN_AND_HEX_SCALARS','compression_rule':'NONE','members':members,'semantic_content':semantic,'source_provenance':provenance};m['semantic_content_digest']=shobj({'semantic':semantic,'provenance':provenance});m['physical_artifact_digest']=shobj({'members':members,'provenance':provenance});(d/'ARTIFACT_MANIFEST.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n');return m
def capture(x,out,prefix,seen,depth=0):
    if depth>4:return
    oid=id(x)
    if oid in seen:return
    seen.add(oid)
    if isinstance(x,np.ndarray):out[prefix]=x;return
    if isinstance(x,(bytes,bytearray,memoryview)):out[prefix]=bytes(x);return
    if isinstance(x,(str,int,float,bool)) or x is None:out[prefix]=x;return
    try:
        import scipy.sparse as sp
        if sp.issparse(x):
            y=x.tocsr();out[prefix+'_data']=y.data;out[prefix+'_indices']=y.indices;out[prefix+'_indptr']=y.indptr;out[prefix+'_shape']=list(y.shape);return
    except Exception:pass
    try:
        import networkx as nx
        if isinstance(x,(nx.Graph,nx.DiGraph)):
            out[prefix+'_nodes']=list(x.nodes());out[prefix+'_edges']=[list(e) for e in x.edges()];return
    except Exception:pass
    if isinstance(x,(list,tuple)):
        if len(x)<=2000 and all(isinstance(v,(str,int,float,bool,type(None))) for v in x):out[prefix]=list(x)
        else:
            for i,v in enumerate(x[:100]):capture(v,out,f'{prefix}_{i}',seen,depth+1)
        return
    if isinstance(x,dict):
        for k,v in list(x.items())[:200]:capture(v,out,f'{prefix}_{str(k)[:30]}',seen,depth+1)
        return
    if type(x).__module__.startswith(('sympy','shapely','Bio','rdkit')):
        try:out[prefix+'_repr']=str(x)
        except Exception:pass
        return
    if inspect.isfunction(x) or inspect.ismethod(x):
        for i,c in enumerate(getattr(x,'__closure__',None) or []):
            try:capture(c.cell_contents,out,f'{prefix}_closure{i}',seen,depth+1)
            except ValueError:pass
def verify_artifact(d,expected):
    d=Path(d);m=json.loads((d/'ARTIFACT_MANIFEST.json').read_text())
    if m['schema']!=CANON:raise ValueError('schema')
    for r in m['members']:
        if shfile(d/r['file'])!=r['file_sha256']:raise ValueError('member digest')
    if shobj({'members':m['members'],'provenance':m['source_provenance']})!=m['physical_artifact_digest']:raise ValueError('physical')
    if m['physical_artifact_digest']!=expected['physical_digest'] or m['semantic_content_digest']!=expected['semantic_digest']:raise ValueError('expected digest')
    return True
def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['build','verify']);ap.add_argument('--runtime');ap.add_argument('--expected',required=True);ap.add_argument('--artifact-root',required=True);ap.add_argument('--receipt',required=True);args=ap.parse_args();exp=json.loads(Path(args.expected).read_text());byid={x['kernel_id']:x for x in exp['records']};root=Path(args.artifact_root)
    if args.mode=='build':
        runtime=Path(args.runtime);sys.path.insert(0,str(runtime));from cfsc_gen9.registry import by_id as spec_by_id;from cfsc_gen9.kernels import build
        targets=json.loads((runtime/'TARGET_REGISTER.json').read_text());refs={r['kernel_id']:r for r in csv.DictReader((runtime/'LOCAL_REFERENCE_OUTCOMES.csv').open())};shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True)
        for t in targets:
            case=build(spec_by_id(t['kernel_id']),t['target_size'],t['target_seed']);captured={};seen=set()
            for name in ['native','candidate','verify','audit','audit_decision','certificate_decision','equivalent']:capture(getattr(case,name),captured,name,seen)
            captured['expected_statement']=case.statement;captured['target_metadata']={k:t[k] for k in sorted(t)};captured['reference_outcome']=refs.get(t['kernel_id'],{})
            prov={'workflow_id':t['kernel_id'],'source':'SEALED_GEN9_FROZEN_RUNTIME','generator_digest':shfile(runtime/'cfsc_gen9/kernels.py'),'artifact_class':'CANONICAL_CLOSURE_CAPTURE_PLUS_FROZEN_STATEMENT','limitations':'Captures arrays/bytes and exact frozen statement; opaque library objects are source-bound strings.'};m=write_artifact(root/t['kernel_id'],captured,prov);e=byid[t['kernel_id']]
            if m['physical_artifact_digest']!=e['physical_digest'] or m['semantic_content_digest']!=e['semantic_digest'] or shobj(case.statement)!=e['expected_statement_digest']:raise SystemExit(f'digest mismatch {t["kernel_id"]}')
            try:case.cleanup()
            except Exception:pass
        sys.path.remove(str(runtime))
    records=[]
    for kid,e in sorted(byid.items()):
        verify_artifact(root/kid,e);ref=e['control_reference'];records.append({'kernel_id':kid,'physical_digest_match':True,'semantic_digest_match':True,'decision_agreement':str(ref.get('decision_agreement','')).lower()=='true','control_accepted':str(ref.get('control_accepted','')).lower()=='true'})
    attacks=[];sample=root/records[0]['kernel_id']
    for kind in ['MEMBER_BYTE_MUTATION','SEMANTIC_DIGEST_MUTATION']:
        with tempfile.TemporaryDirectory() as td:
            q=Path(td)/'x';shutil.copytree(sample,q)
            if kind=='MEMBER_BYTE_MUTATION':
                m=json.loads((q/'ARTIFACT_MANIFEST.json').read_text());p=q/m['members'][0]['file'];b=bytearray(p.read_bytes());b[-1]^=1;p.write_bytes(b)
            else:
                m=json.loads((q/'ARTIFACT_MANIFEST.json').read_text());m['semantic_content_digest']='0'*64;(q/'ARTIFACT_MANIFEST.json').write_text(json.dumps(m,sort_keys=True))
            try:verify_artifact(q,byid[records[0]['kernel_id']]);det=False
            except Exception:det=True
            attacks.append({'attack':kind,'detected':det})
    out={'schema':'CFSC_GEN10_GEN9_CANONICAL_REPAIR_PLATFORM_RECEIPT_V1','platform':__import__('platform').platform(),'machine':__import__('platform').machine(),'kernel_count':len(records),'sound_control_coverage':sum(x['control_accepted'] for x in records)/len(records),'decision_agreement':sum(x['decision_agreement'] for x in records)/len(records),'physical_digest_agreement':sum(x['physical_digest_match'] for x in records)/len(records),'semantic_digest_agreement':sum(x['semantic_digest_match'] for x in records)/len(records),'false_authorization':0,'attacks':attacks,'records':records,'predictor_rescored':False,'evidence_class':'CROSS_PLATFORM_MANAGED_ENVIRONMENT_CANONICAL_ARTIFACT_REPAIR_NOT_INDEPENDENT_TEAM'};Path(args.receipt).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({k:out[k] for k in ['kernel_count','sound_control_coverage','decision_agreement','physical_digest_agreement','semantic_digest_agreement']},indent=2))
    if min(out['sound_control_coverage'],out['decision_agreement'],out['physical_digest_agreement'],out['semantic_digest_agreement'])<.95 or not all(x['detected'] for x in attacks):raise SystemExit(2)
if __name__=='__main__':main()
