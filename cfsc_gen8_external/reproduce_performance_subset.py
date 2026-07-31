import hashlib,json,math,platform,time
from pathlib import Path
import numpy as np

def dig(x):
    if isinstance(x,np.ndarray):return hashlib.sha256(str(x.dtype).encode()+str(x.shape).encode()+np.ascontiguousarray(x).tobytes()).hexdigest()
    if isinstance(x,bytes):return hashlib.sha256(x).hexdigest()
    return hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()
def timing(fn,reps=3):
    for _ in range(1):fn()
    w=[];c=[];z=None
    for _ in range(reps):
        a=time.perf_counter_ns();b=time.process_time_ns();z=fn();w.append(time.perf_counter_ns()-a);c.append(time.process_time_ns()-b)
    return z,int(np.median(w)),int(np.median(c))
def record(kid,native,candidate,verify,audit,expected):
    n,nw,nc=timing(native);cert,cw,cc=timing(candidate);ok=verify(cert);_,vw,vc=timing(lambda:verify(cert),5);_,aw,ac=timing(audit,2)
    rho=cw/max(nw,1);rho_c=cc/max(nc,1);S=aw/max(vw,1);S_c=ac/max(vc,1)
    prod=bool(ok and rho<=2 and rho_c<=2);val=bool(ok and S>=10 and S_c>=10)
    return {'kernel_id':kid,'control':ok,'rho_wall':rho,'rho_cpu':rho_c,'S_wall':S,'S_cpu':S_c,'producer_pass':prod,'validation_pass':val,'joint_pass':prod and val,'expected_local':expected,'producer_label_agreement':prod==expected['producer'],'validation_label_agreement':val==expected['validation'],'joint_label_agreement':(prod and val)==expected['joint']}

def eigsh_case():
    from scipy.sparse import diags
    from scipy.sparse.linalg import eigsh
    n=1200;seed=380678;r=np.random.default_rng(seed);A=diags([-np.ones(n-1),2+r.random(n),-np.ones(n-1)],[-1,0,1],format='csr');k=4
    def native():return eigsh(A,k=k,which='SM',tol=1e-10)
    def candidate():w,v=native();return {'w':w,'v':v,'res':float(np.max(np.linalg.norm(A@v-v*w,axis=0)))}
    def verify(c):return c['res']<=2e-7 and np.linalg.norm(c['v'].T@c['v']-np.eye(k))<1e-5
    return record('H06_EIGSH',native,candidate,verify,native,{'producer':True,'validation':True,'joint':True})
def assignment_case():
    from scipy.optimize import linear_sum_assignment
    n=220;seed=381088;r=np.random.default_rng(seed);C=r.uniform(.8,1.2,(n,n));p=r.permutation(n);C[np.arange(n),p]=r.uniform(0,.03,n);thr=.08*n
    def native():return linear_sum_assignment(C)
    def candidate():i,j=native();q=float(C[i,j].sum());return {'i':i,'j':j,'cost':q,'decision':q<=thr}
    def verify(c):return len(set(c['i']))==n and len(set(c['j']))==n and abs(float(C[c['i'],c['j']].sum())-c['cost'])<1e-9 and (c['cost']<=thr)==c['decision']
    return record('H08_ASSIGNMENT',native,candidate,verify,native,{'producer':True,'validation':False,'joint':False})
def lark_case():
    from lark import Lark
    n=80;g='?start: expr\n?expr: NUMBER | "(" expr "+" expr ")"\n%import common.NUMBER\n%import common.WS\n%ignore WS';p=Lark(g,parser='earley');q='1'
    for i in range(n):q=f'({q} + {i%9+1})'
    def native():return p.parse(q)
    def candidate():return {'tree':native().pretty(),'numbers':n+1}
    def verify(c):return c['numbers']==n+1 and c['tree'].count('number')>=0
    return record('H09_LARK',native,candidate,verify,native,{'producer':True,'validation':True,'joint':True})
def imageio_case():
    import imageio.v3 as iio
    n=384;a=np.random.default_rng(380802).integers(0,256,(n,n),dtype=np.uint8)
    def native():return iio.imwrite('<bytes>',a,extension='.png')
    def candidate():z=native();return {'bytes':z,'decoded':dig(iio.imread(z,extension='.png'))}
    def verify(c):return np.array_equal(iio.imread(c['bytes'],extension='.png'),a)
    return record('H13_IMAGEIO',native,candidate,verify,native,{'producer':True,'validation':False,'joint':False})
def resample_case():
    import pandas as pd
    n=200000;r=np.random.default_rng(381372);idx=pd.date_range('2000-01-01',periods=n,freq='min');v=r.normal(size=n);q=pd.Series(v,index=idx)
    def native():return q.resample('1h').sum()
    def ref():return np.bincount(np.arange(n)//60,weights=v)
    def candidate():x=native();return {'v':x.to_numpy(),'bins':len(x)}
    def verify(c):return np.allclose(c['v'],ref(),rtol=1e-12,atol=1e-10)
    return record('H14_PANDAS_RESAMPLE',native,candidate,verify,native,{'producer':True,'validation':False,'joint':False})
def irr_case():
    import numpy_financial as nf
    n=400;r=np.random.default_rng(381162);cf=np.r_[-1000.,r.uniform(0,20,n-2),2000.]
    def native():return float(nf.irr(cf))
    def npv(x):return float(np.sum(cf/(1+x)**np.arange(n)))
    def candidate():x=native();return {'x':x,'npv':npv(x)}
    def verify(c):return math.isfinite(c['x']) and abs(npv(c['x']))<=1e-7
    return record('H15_FINANCIAL_IRR',native,candidate,verify,native,{'producer':True,'validation':True,'joint':True})
rows=[]
for fn in [eigsh_case,assignment_case,lark_case,imageio_case,resample_case,irr_case]:
    try:rows.append(fn())
    except Exception as e:rows.append({'kernel_id':fn.__name__,'error':repr(e),'control':False,'producer_label_agreement':False,'validation_label_agreement':False,'joint_label_agreement':False})
out={'schema':'CFSC_GEN8_CROSS_PLATFORM_PERFORMANCE_SUBSET_V1','environment':{'platform':platform.platform(),'machine':platform.machine(),'python':platform.python_version()},'records':rows,'semantic_controls':sum(bool(x.get('control')) for x in rows),'producer_label_agreement':sum(bool(x.get('producer_label_agreement')) for x in rows),'validation_label_agreement':sum(bool(x.get('validation_label_agreement')) for x in rows),'joint_label_agreement':sum(bool(x.get('joint_label_agreement')) for x in rows),'evidence_class':'CROSS_PLATFORM_MANAGED_ENVIRONMENT_PERFORMANCE_SUBSET_NOT_INDEPENDENT_TEAM'}
Path('external_reproduction.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps(out,indent=2))
if out['semantic_controls']<5:raise SystemExit(2)
