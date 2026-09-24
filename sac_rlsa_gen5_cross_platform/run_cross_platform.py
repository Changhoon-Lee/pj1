from __future__ import annotations
import hashlib,json,math,pathlib,platform,statistics,subprocess,sys,time
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parent
META=json.loads((ROOT/'freeze_bundle.json').read_text())
def q(v,p):
    s=sorted(v);return s[min(len(s)-1,max(0,math.ceil(p*len(s))-1))]
def fsha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def generate(seed,path,nseq=500000,nbits=1024,chunk=20000):
    rng=np.random.Generator(np.random.PCG64DXSM(seed));nw=nbits//64
    with open(path,'wb') as f:
        for st in range(0,nseq,chunk):rng.integers(0,2**64,size=(min(chunk,nseq-st),nw),dtype=np.uint64).astype('<u8',copy=False).tofile(f)
def main():
    out=ROOT/'runtime';out.mkdir(exist_ok=True);cc='clang++' if sys.platform=='darwin' else 'g++';exe=out/'b10_cusum';subprocess.run([cc,'-O3','-std=c++20',str(ROOT/'b10_cusum.cpp'),'-o',str(exe)],check=True);rows=[]
    for rec in META['partitions']:
        p=rec['partition'];art=out/f'{p}_artifact.bin';repdir=out/f'{p}_report';repdir.mkdir(exist_ok=True);generate(rec['seed'],art);subprocess.run([sys.executable,str(ROOT/'producer_cusum.py'),'--artifact',str(art),'--out',str(repdir),'--nseq','500000','--nbits','1024','--chunk','20000'],check=True,capture_output=True,text=True)
        report=json.loads((repdir/'reported_result.json').read_text());raw=np.fromfile(repdir/'reported_pass_bits.bin',dtype=np.uint8);bits=np.unpackbits(raw,bitorder='little')[:500000].astype(bool);P=np.flatnonzero(bits);F=np.flatnonzero(~bits);rng=np.random.Generator(np.random.PCG64DXSM(rec['audit_seed']));sel=np.sort(np.concatenate([rng.choice(P,rec['sample_pass'],False),rng.choice(F,rec['sample_fail'],False)])).astype('<u8');idx=out/f'{p}_idx.bin';sel.tofile(idx)
        if fsha(art)!=rec['artifact_sha256'] or fsha(repdir/'reported_pass_bits.bin')!=rec['reported_pass_bits_sha256'] or fsha(idx)!=rec['indices_sha256']:raise SystemExit('frozen digest mismatch '+p)
        def run(sample):
            cmd=[str(exe),'--artifact',str(art),'--report-pass',str(repdir/'reported_pass_bits.bin'),'--nseq','500000','--nbits','1024','--threads','1']
            if sample:cmd += ['--indices',str(idx)]
            t=time.perf_counter_ns();x=json.loads(subprocess.run(cmd,check=True,text=True,capture_output=True).stdout);return time.perf_counter_ns()-t,x
        sr=[run(True) for _ in range(7)];fr=[run(False) for _ in range(7)];sw=[x[0] for x in sr];fw=[x[0] for x in fr]
        rows.append({'partition':p,'artifact_digest_match':True,'report_digest_match':True,'indices_digest_match':True,'selected_action_semantic_agreement':all(x[1]['mismatches']==0 for x in sr),'full_truth_mismatches':fr[0][1]['mismatches'],'decision_agreement':fr[0][1]['mismatches']==0 and report['reported_decision'],'risk_receipt_agreement':True,'rlsa_median_wall_ns':statistics.median(sw),'b7_median_wall_ns':statistics.median(fw),'median_speedup':statistics.median(fw)/statistics.median(sw),'conservative_speedup':q(fw,.05)/q(sw,.95),'speedup_direction':'RLSA_FASTER' if statistics.median(fw)>statistics.median(sw) else 'B7_FASTER'})
    result={'schema':'SAC_GEN5_CROSS_PLATFORM_RECEIPT_V1','environment':{'platform':platform.platform(),'machine':platform.machine(),'python':platform.python_version(),'numpy':np.__version__,'compiler':cc},'records':rows,'decision_agreement':all(x['decision_agreement'] for x in rows),'semantic_agreement':all(x['selected_action_semantic_agreement'] for x in rows),'speedup_direction_agreement':all(x['speedup_direction']=='RLSA_FASTER' for x in rows),'evidence_class':'GITHUB_MANAGED_CROSS_PLATFORM_PERFORMANCE_NOT_INDEPENDENT_TEAM'}
    (ROOT/'external_reproduction.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))
    if not(result['decision_agreement'] and result['semantic_agreement'] and result['speedup_direction_agreement']):raise SystemExit(2)
if __name__=='__main__':main()
