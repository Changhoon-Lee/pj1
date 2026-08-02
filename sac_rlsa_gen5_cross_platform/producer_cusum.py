from __future__ import annotations
import argparse,hashlib,json,math,pathlib,resource,time
import numpy as np
from numba import njit,prange
@njit(cache=False)
def phi(x):return .5*(1+math.erf(x/math.sqrt(2.)))
@njit(cache=False)
def pvalue(n,z):
    if z<=0:return 1.
    sq=math.sqrt(n);s1=0.;s2=0.;a=math.floor((-n/z+1.)/4.);b=math.floor((n/z-1.)/4.)
    for k in range(a,b+1):s1+=phi((4*k+1)*z/sq)-phi((4*k-1)*z/sq)
    a=math.floor((-n/z-3.)/4.);b=math.floor((n/z-1.)/4.)
    for k in range(a,b+1):s2+=phi((4*k+3)*z/sq)-phi((4*k+1)*z/sq)
    return min(1.,max(0.,1.-s1+s2))
@njit(parallel=True,cache=False)
def evaluate(words,nbits):
    m=words.shape[0];passed=np.empty(m,np.uint8);zs=np.empty(m,np.uint16)
    for i in prange(m):
        s=0;z=0
        for j in range(words.shape[1]):
            x=words[i,j]
            for b in range(64):
                s+=1 if ((x>>b)&1) else -1;aa=s if s>=0 else -s
                if aa>z:z=aa
        zs[i]=z;passed[i]=1 if pvalue(nbits,z)>=.01 else 0
    return zs,passed
def fsha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--artifact',required=True);ap.add_argument('--out',required=True);ap.add_argument('--nseq',type=int,required=True);ap.add_argument('--nbits',type=int,required=True);ap.add_argument('--chunk',type=int,default=20000);a=ap.parse_args();o=pathlib.Path(a.out);o.mkdir(parents=True,exist_ok=True);nw=a.nbits//64
    evaluate(np.zeros((1,nw),dtype=np.uint64),a.nbits);mm=np.memmap(a.artifact,dtype='<u8',mode='r',shape=(a.nseq,nw));ps=np.empty(a.nseq,np.uint8);zs=np.empty(a.nseq,np.uint16);w0=time.perf_counter_ns();c0=time.process_time_ns()
    for st in range(0,a.nseq,a.chunk):
        z,p=evaluate(np.asarray(mm[st:st+a.chunk]),a.nbits);zs[st:st+len(p)]=z;ps[st:st+len(p)]=p
    wall=time.perf_counter_ns()-w0;cpu=time.process_time_ns()-c0;np.packbits(ps,bitorder='little').tofile(o/'reported_pass_bits.bin');zs.astype('<u2').tofile(o/'reported_z_u16le.bin');alpha=.01;ph=.99;lo=ph-3*math.sqrt(ph*(1-ph)/a.nseq);hi=ph+3*math.sqrt(ph*(1-ph)/a.nseq);pc=int(ps.sum());prop=pc/a.nseq
    result={'schema':'SAC_GEN5_NIST_CUSUM_REPORT_V1','test':'NIST_SP800_22_REV1A_CUMULATIVE_SUMS_FORWARD','nseq':a.nseq,'nbits':a.nbits,'sequence_alpha':alpha,'pass_proportion_lower':lo,'pass_proportion_upper':hi,'reported_pass_count':pc,'reported_pass_proportion':prop,'reported_decision':bool(lo<=prop<=hi),'artifact_sha256':fsha(a.artifact),'reported_pass_bits.bin_sha256':fsha(o/'reported_pass_bits.bin'),'reported_z_u16le.bin_sha256':fsha(o/'reported_z_u16le.bin'),'wall_ns':wall,'cpu_ns':cpu,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'producer':'Numba independent forward-Cusum implementation'}
    (o/'reported_result.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
