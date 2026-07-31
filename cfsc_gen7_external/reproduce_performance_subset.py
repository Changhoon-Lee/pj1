from __future__ import annotations
import json, math, platform, statistics, time
from pathlib import Path
import numpy as np

CASES=[
 ('H05_OPTEINSUM_CHAIN5',776395229,260,False,False),
 ('H06_OPENCV_HOMOGRAPHY_RANSAC',1561641605,22000,True,True),
 ('H07_OPENCV_PNP_RANSAC',1880319832,9000,True,False),
 ('H08_NASHPY_SUPPORT_ENUM',1031535930,7,True,True),
 ('H09_SCIPY_LINEAR_LEAST_SQUARES',1326793077,2600,True,True),
 ('H12_SCIPY_STRONGLY_CONVEX_MINIMIZE',396184791,280,True,True),
]

def med(fn,reps=3,warm=1):
 for _ in range(warm): fn()
 xs=[]; last=None
 for _ in range(reps):
  t=time.perf_counter_ns(); last=fn(); xs.append(time.perf_counter_ns()-t)
 return last,statistics.median(xs)

def allclose(a,b,rtol=1e-8,atol=1e-10):
 return bool(np.allclose(np.asarray(a),np.asarray(b),rtol=rtol,atol=atol,equal_nan=True))

def opt_chain5(n,seed):
 import opt_einsum as oe
 rng=np.random.default_rng(seed); mats=[rng.normal(size=(n,n)) for _ in range(5)]; expr='ab,bc,cd,de,ef->af'; tol=2e-7
 def native(): return oe.contract(expr,*mats,optimize='optimal')
 def candidate(): return native()
 def verify(Y):
  for j in range(8):
   r=np.random.default_rng(seed+10000+j).normal(size=n); z=r
   for M in reversed(mats[1:]): z=M@z
   left=mats[0]@z; right=Y@r
   if np.linalg.norm(left-right)>tol*max(1.0,np.linalg.norm(left)): return False
  return True
 return native,candidate,verify,native,lambda y,a:allclose(y,a,2e-7,2e-8)

def homography(n,seed):
 import cv2
 rng=np.random.default_rng(seed); src=rng.uniform(-1,1,size=(n,2)).astype(np.float32); H0=np.array([[1.05,.08,.2],[-.04,.97,-.15],[.015,-.01,1]],float); z=np.c_[src,np.ones(n)]@H0.T; dst=(z[:,:2]/z[:,2:]).astype(np.float32); dst+=rng.normal(scale=.002,size=dst.shape).astype(np.float32); idx=rng.choice(n,size=n//4,replace=False); dst[idx]=rng.uniform(-1.5,1.5,size=(len(idx),2)); thr=.012; required=.70
 def native(): cv2.setRNGSeed(seed%2147483647); return cv2.findHomography(src,dst,cv2.RANSAC,thr,maxIters=3000,confidence=.999)
 def candidate():
  H,_=native(); zh=np.c_[src,np.ones(n)]@H.T; err=np.linalg.norm(zh[:,:2]/zh[:,2:]-dst,axis=1); return H,bool(np.mean(err<=thr)>=required),int(np.sum(err<=thr))
 def verify(c):
  H,d,k=c; zh=np.c_[src,np.ones(n)]@H.T; err=np.linalg.norm(zh[:,:2]/zh[:,2:]-dst,axis=1); return bool(np.mean(err<=thr)>=required)==d and int(np.sum(err<=thr))==k
 return native,candidate,verify,native,lambda c,a:verify(c)

def pnp(n,seed):
 import cv2
 rng=np.random.default_rng(seed); obj=rng.uniform(-1,1,size=(n,3)).astype(np.float32); K=np.array([[900,0,320],[0,910,240],[0,0,1]],float); r0=np.array([.15,-.08,.2]); t0=np.array([.1,-.2,5.]); img,_=cv2.projectPoints(obj,r0,t0,K,None); img=img.reshape(-1,2).astype(np.float32); img+=rng.normal(scale=.35,size=img.shape).astype(np.float32); idx=rng.choice(n,size=n//5,replace=False); img[idx]=rng.uniform([0,0],[640,480],size=(len(idx),2)); thr=2.; required=.72
 def native(): cv2.setRNGSeed(seed%2147483647); return cv2.solvePnPRansac(obj,img,K,None,iterationsCount=2500,reprojectionError=thr,confidence=.999,flags=cv2.SOLVEPNP_EPNP)
 def candidate():
  ok,r,t,_=native(); pred,_=cv2.projectPoints(obj,r,t,K,None); err=np.linalg.norm(pred.reshape(-1,2)-img,axis=1); return r,t,bool(ok and np.mean(err<=thr)>=required),int(np.sum(err<=thr))
 def verify(c):
  r,t,d,k=c; pred,_=cv2.projectPoints(obj,r,t,K,None); err=np.linalg.norm(pred.reshape(-1,2)-img,axis=1); return bool(np.mean(err<=thr)>=required)==d and int(np.sum(err<=thr))==k
 return native,candidate,verify,native,lambda c,a:verify(c)

def nash_case(n,seed):
 import nashpy as nash
 rng=np.random.default_rng(seed); A=rng.normal(size=(n,n)); B=rng.normal(size=(n,n)); A+=np.diag(np.linspace(.2,1.1,n)); B+=np.diag(np.linspace(1.1,.2,n)); g=nash.Game(A,B); tol=2e-6
 def native(): return list(g.support_enumeration(non_degenerate=False,tol=1e-12))
 def candidate():
  s=native(); return s[0] if s else (np.full(n,np.nan),np.full(n,np.nan))
 def verify(c):
  sr,sc=map(lambda x:np.asarray(x,float),c)
  if np.any(sr<-tol) or np.any(sc<-tol) or abs(sr.sum()-1)>tol or abs(sc.sum()-1)>tol: return False
  rp=A@sc; cp=sr@B; u=float(sr@rp); v=float(cp@sc); return float(rp.max()-u)<=tol and float(cp.max()-v)<=tol
 return native,candidate,verify,native,lambda c,a:bool(a) and verify(c)

def least_squares(m,seed):
 from scipy.optimize import least_squares
 n=max(30,int(math.sqrt(m)*1.6)); rng=np.random.default_rng(seed); A=rng.normal(size=(m,n)); x0=rng.normal(size=n); b=A@x0+rng.normal(scale=.02,size=m); start=np.zeros(n); tol=4e-7
 def fun(x): return A@x-b
 def jac(x): return A
 def native(): return least_squares(fun,start,jac=jac,method='trf',gtol=1e-10,xtol=1e-12,ftol=1e-12,max_nfev=80)
 def candidate():
  r=native(); return r.x,bool(r.success),float(np.linalg.norm(A.T@(A@r.x-b)))
 def verify(c): return c[1] and np.linalg.norm(A.T@(A@c[0]-b))<=tol*max(1.,np.linalg.norm(A.T@b))
 return native,candidate,verify,native,lambda c,a:allclose(c[0],a.x,2e-5,2e-6)

def minimize_case(n,seed):
 from scipy.optimize import minimize
 rng=np.random.default_rng(seed); M=rng.normal(size=(n,n)); Q=(M@M.T)/n+.5*np.eye(n); b=rng.normal(size=n); x0=np.zeros(n); tol=2e-6
 def f(x): return .5*x@Q@x-b@x
 def g(x): return Q@x-b
 def native(): return minimize(f,x0,jac=g,method='BFGS',options={'gtol':1e-8,'maxiter':600,'disp':False})
 def candidate():
  r=native(); return r.x,bool(r.success or np.linalg.norm(g(r.x))<1e-5),float(np.linalg.norm(g(r.x)))
 def verify(c): return c[1] and np.linalg.norm(g(c[0]))<=tol*max(1.,np.linalg.norm(b))
 return native,candidate,verify,native,lambda c,a:allclose(c[0],a.x,2e-5,2e-6)

BUILD={'H05_OPTEINSUM_CHAIN5':opt_chain5,'H06_OPENCV_HOMOGRAPHY_RANSAC':homography,'H07_OPENCV_PNP_RANSAC':pnp,'H08_NASHPY_SUPPORT_ENUM':nash_case,'H09_SCIPY_LINEAR_LEAST_SQUARES':least_squares,'H12_SCIPY_STRONGLY_CONVEX_MINIMIZE':minimize_case}
rows=[]
for kid,seed,size,local_p,local_v in CASES:
 native,candidate,verify,audit,equiv=BUILD[kid](size,seed)
 _,tn=med(native,3,1); cert,tc=med(candidate,3,1); ok,tv=med(lambda:bool(verify(cert)),5,1); aud,ta=med(audit,2,1)
 correct=bool(ok and equiv(cert,aud)); rho=tc/max(1,tn); S=ta/max(1,tv); p=bool(correct and rho<=2); v=bool(correct and S>=10)
 rows.append({'kernel_id':kid,'rho_wall':rho,'validation_advantage_wall':S,'correct_control':correct,'producer_pass':p,'validation_pass':v,'joint_pass':p and v,'local_producer_pass':local_p,'local_validation_pass':local_v,'producer_label_match':p==local_p,'validation_label_match':v==local_v,'joint_label_match':(p and v)==(local_p and local_v)})
summary={'schema':'CFSC_GEN7_CROSS_PLATFORM_PERFORMANCE_SUBSET_V1','environment':{'platform':platform.platform(),'machine':platform.machine(),'python':platform.python_version()},'rows':rows,'semantic_controls_pass':sum(r['correct_control'] for r in rows),'producer_label_matches':sum(r['producer_label_match'] for r in rows),'validation_label_matches':sum(r['validation_label_match'] for r in rows),'joint_label_matches':sum(r['joint_label_match'] for r in rows)}
summary['platform_pass']=summary['semantic_controls_pass']==6 and summary['producer_label_matches']>=5 and summary['validation_label_matches']>=5 and summary['joint_label_matches']>=5
Path('external_reproduction.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
print(json.dumps({'platform':summary['environment'],'pass':summary['platform_pass'],'producer_matches':summary['producer_label_matches'],'validation_matches':summary['validation_label_matches'],'joint_matches':summary['joint_label_matches']},indent=2))
