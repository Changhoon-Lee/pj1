from __future__ import annotations
import json,platform,sys
import numpy as np
import scipy.linalg as sla
import scipy.ndimage as ndi
import scipy.signal as signal
import scipy.sparse as sp
import networkx as nx
import xarray as xr
import sympy as sy
import mpmath as mp
import statsmodels.api as sm
from skimage.measure import label
from skimage.transform import hough_line
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from Bio import Align
from rdkit import Chem
rng=np.random.default_rng(6060);results=[]
def check(name,fn):
 try:results.append({'kernel':name,'pass':bool(fn()),'error':None})
 except Exception as e:results.append({'kernel':name,'pass':False,'error':repr(e)})
def sig(z):return 1/(1+np.exp(-z))
A=rng.integers(-2,3,(16,16));B=rng.integers(-2,3,(16,16));C=A@B;check('K01_NUMPY_GEMM',lambda:np.array_equal(A@(B@np.arange(16)),C@np.arange(16)))
M=rng.normal(size=(30,30));SPD=M@M.T+30*np.eye(30);b=rng.normal(size=30);cf,lo=sla.cho_factor(SPD);x=sla.cho_solve((cf,lo),b);check('K02_SCIPY_CHOLESKY_SOLVE',lambda:np.linalg.norm(SPD@x-b)<1e-9)
W=sp.random(100,100,density=.05,random_state=1,format='csr');v=rng.normal(size=100);y=W@v;check('K03_SCIPY_SPARSE_MATVEC',lambda:np.allclose(y,W.dot(v)))
G=nx.DiGraph();G.add_edge(0,1,capacity=3);G.add_edge(0,2,capacity=2);G.add_edge(1,3,capacity=2);G.add_edge(2,3,capacity=3);fv,_=nx.maximum_flow(G,0,3);cv,_=nx.minimum_cut(G,0,3);check('K04_NETWORKX_MAXFLOW',lambda:fv==cv==4)
UG=nx.Graph();UG.add_weighted_edges_from([(0,1,1),(1,2,2),(0,2,5),(2,3,1)]);T=nx.minimum_spanning_tree(UG);check('K05_NETWORKX_MST',lambda:nx.is_tree(T) and T.size(weight='weight')==4)
a=np.array([1,2,3],dtype=np.int64);bb=np.array([4,-1],dtype=np.int64);cc=signal.convolve(a,bb,method='direct');check('K06_SCIPY_EXACT_CONVOLUTION',lambda:np.array_equal(cc,np.array([4,7,10,-3])))
img=np.array([[1,0,1],[1,0,0],[0,1,1]],bool);lab=label(img,connectivity=1);check('K07_SKIMAGE_CONNECTED_COMPONENTS',lambda:int(lab.max())==3)
X=rng.normal(size=(200,8));coef0=rng.normal(size=8);yy=X@coef0;ridge=Ridge(alpha=2,fit_intercept=False).fit(X,yy);check('K08_SKLEARN_RIDGE',lambda:np.linalg.norm(X.T@(X@ridge.coef_-yy)+2*ridge.coef_)<1e-6)
cent=np.array([[-3,-3],[3,3]],float);Xk=np.vstack([cent[0]+rng.normal(scale=.1,size=(100,2)),cent[1]+rng.normal(scale=.1,size=(100,2))]);km=KMeans(n_clusters=2,n_init=1,random_state=0).fit(Xk);check('K09_SKLEARN_KMEANS',lambda:len(np.unique(km.labels_))==2)
z=sy.symbols('z');poly=(z+1)*(z**2+z+1);fac=sy.factor_list(poly);check('K10_SYMPY_POLY_FACTOR',lambda:sy.expand(fac[0]*sy.prod(f**e for f,e in fac[1]))==sy.expand(poly))
mol=Chem.MolFromSmiles('CCOc1ccccc1');pat=Chem.MolFromSmarts('c1ccccc1');match=mol.GetSubstructMatch(pat);check('K11_RDKIT_SUBSTRUCTURE',lambda:len(match)==6)
da=xr.DataArray([1.,2.,3.],dims=['x']);ww=xr.DataArray([1.,1.,2.],dims=['x']);check('K12_XARRAY_WEIGHTED_MEAN',lambda:abs(float(da.weighted(ww).mean())-2.25)<1e-12)
S=rng.normal(size=(20,20));S=(S+S.T)/2;ew,EV=sla.eigh(S);check('H01_SCIPY_FULL_EIGH',lambda:np.linalg.norm(S@EV-EV*ew)<1e-9)
A2=rng.normal(size=(80,10));x2=rng.normal(size=10);b2=A2@x2;Q,R=np.linalg.qr(A2,mode='reduced');xh=np.linalg.solve(R,Q.T@b2);check('H02_NUMPY_QR_LEAST_SQUARES',lambda:np.linalg.norm(A2@xh-b2)<1e-9)
WG=nx.Graph();WG.add_weighted_edges_from([(0,1,1),(1,2,2),(0,2,5),(2,3,1)]);dist,_=nx.single_source_dijkstra(WG,0);check('H03_NETWORKX_SHORTEST_PATH',lambda:dist[3]==4)
BG=nx.complete_bipartite_graph(5,5);left=set(range(5));mat=nx.algorithms.bipartite.hopcroft_karp_matching(BG,top_nodes=left);cover=left;check('H04_NETWORKX_BIPARTITE_MATCHING',lambda:len(mat)//2==len(cover)==5 and all(u in cover or v in cover for u,v in BG.edges()))
g=ndi.gaussian_filter(np.eye(20),1.2);check('H05_SCIPY_GAUSSIAN_FILTER',lambda:g.shape==(20,20) and np.isfinite(g).all())
h,th,d=hough_line(np.eye(20,dtype=bool));check('H06_SKIMAGE_HOUGH_LINE',lambda:h.shape==(len(d),len(th)))
Xp=rng.normal(size=(150,12));pca=PCA(n_components=12,svd_solver='full').fit(Xp);check('H07_SKLEARN_FULL_PCA',lambda:np.linalg.norm(pca.components_@pca.components_.T-np.eye(12))<1e-9)
Xl=rng.normal(size=(500,6));w0=rng.normal(scale=.2,size=6);yl=(rng.random(500)<sig(Xl@w0)).astype(int);lr=LogisticRegression(C=1,fit_intercept=False,solver='lbfgs',max_iter=300,tol=1e-10).fit(Xl,yl);w=lr.coef_[0];grad=Xl.T@(sig(Xl@w)-yl)/len(yl)+w/len(yl);check('H08_SKLEARN_LOGISTIC_REGRESSION',lambda:np.linalg.norm(grad)<1e-5)
df=sm.datasets.elnino.load_pandas().data;years=df['YEAR'].to_numpy(float);annual=df.drop(columns=['YEAR']).to_numpy(float).mean(axis=1);XX=np.column_stack([np.ones(len(years)),years-years.mean()]);fit=sm.OLS(annual,XX).fit();decision=abs(fit.params[1])>=.005 and fit.pvalues[1]<=.05;check('H09_STATSMODELS_ELNINO_OLS_DECISION',lambda:bool(decision))
al=Align.PairwiseAligner();al.mode='global';al.match_score=2;al.mismatch_score=-1;al.open_gap_score=-2;al.extend_gap_score=-2;check('H10_BIOPYTHON_PAIRWISE_ALIGNMENT',lambda:al.score('ACGT','ACCT')==5)
rw=Chem.RWMol();ids=[rw.AddAtom(Chem.Atom(6)) for _ in range(12)];[rw.AddBond(ids[i],ids[(i+1)%12],Chem.BondType.SINGLE) for i in range(12)];rm=rw.GetMol();Chem.SanitizeMol(rm);rings=Chem.GetSymmSSSR(rm);check('H11_RDKIT_MACROCYCLE_DECISION',lambda:any(len(r)==12 for r in rings))
with mp.workdps(60):root=mp.findroot(lambda q:q**3-q-2,(mp.mpf('1.5'),mp.mpf('1.6')));eps=mp.mpf('1e-25');aa_s=str(root-eps);bbb_s=str(root+eps)
def root_check():
 with mp.workdps(60):
  aa=mp.mpf(aa_s);bbb=mp.mpf(bbb_s);return aa**3-aa-2<0<bbb**3-bbb-2 and 3*aa*aa-1>0
check('H12_MPMATH_INTERVAL_ROOT',root_check)
out={'schema':'CFSC_GEN6_EXTERNAL_SEMANTIC_REPRODUCTION_V1','platform':platform.platform(),'python':sys.version,'registered':len(results),'passed':sum(r['pass'] for r in results),'all_pass':all(r['pass'] for r in results),'results':results};open('external_reproduction.json','w').write(json.dumps(out,indent=2,sort_keys=True));print(json.dumps({'registered':out['registered'],'passed':out['passed'],'all_pass':out['all_pass'],'platform':out['platform']}));sys.exit(0 if out['all_pass'] else 1)
