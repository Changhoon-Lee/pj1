import csv, io, json, math, hashlib, urllib.request, zipfile
from pathlib import Path
UA={'User-Agent':'Mozilla/5.0 R39-academic-research'}
def fetch(url,timeout=180):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=timeout) as r: b=r.read()
    return b,hashlib.sha256(b).hexdigest()
def clean(x): return x.strip().strip('"').strip()
def f(x):
    try:return float(clean(x))
    except:return None
def csvrows(b): return list(csv.reader(io.StringIO(b.decode('utf-8-sig',errors='replace'))))
def quant(a,p):
    a=sorted(a); j=(len(a)-1)*p; lo=int(j); hi=min(lo+1,len(a)-1); w=j-lo
    return a[lo]*(1-w)+a[hi]*w
def stats(a):
    a=[x for x in a if x is not None and math.isfinite(x)]
    if not a:return {'n':0,'mean':None,'sd':None,'min':None,'p10':None,'p25':None,'median':None,'p75':None,'p90':None,'max':None}
    mean=sum(a)/len(a)
    return {'n':len(a),'mean':mean,'sd':(sum((x-mean)**2 for x in a)/(len(a)-1))**.5 if len(a)>1 else 0,
            'min':min(a),'p10':quant(a,.1),'p25':quant(a,.25),'median':quant(a,.5),'p75':quant(a,.75),'p90':quant(a,.9),'max':max(a)}
ny={}
for market,url in {'DA':'https://mis.nyiso.com/public/csv/damlbmp/20260501damlbmp_gen_csv.zip',
                   'RT':'https://mis.nyiso.com/public/csv/rtlbmp/20260501rtlbmp_gen_csv.zip'}.items():
    b,sha=fetch(url); z=zipfile.ZipFile(io.BytesIO(b)); obs={}; headers=None
    for nm in z.namelist():
        if not nm.lower().endswith('.csv'): continue
        rr=csvrows(z.read(nm))
        if not rr: continue
        h=[clean(x) for x in rr[0]]; headers=h; ix={x:i for i,x in enumerate(h)}
        for r in rr[1:]:
            if not r: continue
            name=clean(r[ix['Name']]); ptid=clean(r[ix['PTID']])
            if name!='N.E._GEN_SANDY PD' and ptid!='24062': continue
            ts=clean(r[ix['Time Stamp']]); lb=f(r[ix['LBMP ($/MWHr)']]); loss=f(r[ix['Marginal Cost Losses ($/MWHr)']]); cong=f(r[ix['Marginal Cost Congestion ($/MWHr)']])
            # NYISO raw convention: LBMP = energy + losses - raw congestion.
            stripped=lb+cong
            obs[ts]={'lmp':lb,'raw_congestion':cong,'loss':loss,'congestion_stripped':stripped}
    ny[market]={'url':url,'sha256':sha,'header':headers,'obs':obs,'n':len(obs)}
ne={'DA':{'obs':{},'sources':[]},'RT':{'obs':{},'sources':[]}}
for day in range(1,32):
    ds=f'202605{day:02d}'
    for market,url in {'DA':f'https://www.iso-ne.com/static-transform/csv/histRpts/da-lmp/WW_DALMP_ISO_{ds}.csv',
                       'RT':f'https://www.iso-ne.com/static-transform/csv/histRpts/rt-lmp/lmp_rt_final_{ds}.csv'}.items():
        try:b,sha=fetch(url)
        except Exception as e:
            ne[market]['sources'].append({'day':ds,'url':url,'error':repr(e)});continue
        ne[market]['sources'].append({'day':ds,'url':url,'sha256':sha,'bytes':len(b)})
        rr=csvrows(b)
        for r in rr:
            if not r or r[0]!='D' or len(r)<10:continue
            if clean(r[3])!='4011' and clean(r[4])!='.I.ROSETON 345 1':continue
            date=clean(r[1]); he=int(clean(r[2])); lmp=f(r[6]); energy=f(r[7]); cong=f(r[8]); loss=f(r[9])
            stripped=lmp-cong
            ne[market]['obs'][f'{date}|{he:02d}']={'lmp':lmp,'congestion':cong,'loss':loss,'energy':energy,'congestion_stripped':stripped}
def ny_hour_map(obs):
    import datetime as dt
    out={}
    for ts,v in obs.items():
        parsed=None
        for fmt in ['%m/%d/%Y %H:%M','%m/%d/%Y %H:%M:%S','%d%b%Y:%H:%M:%S']:
            try:parsed=dt.datetime.strptime(ts,fmt);break
            except:pass
        if parsed is None:continue
        out[f"{parsed.strftime('%m/%d/%Y')}|{parsed.hour+1:02d}"]=v
    return out
nym={m:ny_hour_map(ny[m]['obs']) for m in ['DA','RT']}
keys=sorted(set(nym['DA'])&set(nym['RT'])&set(ne['DA']['obs'])&set(ne['RT']['obs']))
rows=[]
for k in keys:
    da_ny=nym['DA'][k]['congestion_stripped']; da_ne=ne['DA']['obs'][k]['congestion_stripped']
    rt_ny=nym['RT'][k]['congestion_stripped']; rt_ne=ne['RT']['obs'][k]['congestion_stripped']
    da_spread=da_ne-da_ny; d=1 if da_spread>=0 else -1; s=d*da_spread
    rt_spread=rt_ne-rt_ny; T=d*rt_spread
    rows.append({'key':k,'direction':'NY_TO_NE' if d==1 else 'NE_TO_NY','s_DA_usd_per_mwh':s,'T_RT_same_direction_usd_per_mwh':T,
                 'option_destruction_wedge_s_minus_T':s-T,'DA_raw_spread_NE_minus_NY':da_spread,'RT_raw_spread_NE_minus_NY':rt_spread,
                 'direction_reversal':da_spread*rt_spread<0})
result={'schema':'R39_ELECTRICITY_DIRECT_MONETARY_MEASUREMENT_V1',
'interpretation':{'NY_proxy':'N.E._GEN_SANDY PD, PTID 24062','NE_proxy':'.I.ROSETON 345 1, Location ID 4011',
'price_object':'congestion-stripped proxy LMP = energy + marginal loss component',
's':'day-ahead marginal gains from trade per MWh in the day-ahead efficient direction',
'T':'final real-time marginal gains from trade per MWh evaluated in the same precommitted direction',
'wedge':'s-T, monetary option-destruction wedge for a fixed-direction marginal cross-border MWh',
'causal_claim':'NONE; direct measurement, not a causal W2-CQ test'},
'source_summary':{'NYISO':{m:{k:v for k,v in ny[m].items() if k!='obs'} for m in ny},
'ISONE':{m:{'source_count':len(ne[m]['sources']),'sources':ne[m]['sources']} for m in ne}},
'matched_hours':len(rows),'s_stats':stats([r['s_DA_usd_per_mwh'] for r in rows]),
'T_stats':stats([r['T_RT_same_direction_usd_per_mwh'] for r in rows]),
'wedge_stats':stats([r['option_destruction_wedge_s_minus_T'] for r in rows]),
'share_T_positive':sum(r['T_RT_same_direction_usd_per_mwh']>0 for r in rows)/len(rows) if rows else None,
'share_wedge_positive':sum(r['option_destruction_wedge_s_minus_T']>0 for r in rows)/len(rows) if rows else None,
'direction_reversal_share':sum(r['direction_reversal'] for r in rows)/len(rows) if rows else None,
'rows':rows}
Path('r39_electricity/DIRECT_MONETARY_MEASUREMENT_MAY2026.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:result[k] for k in ['matched_hours','s_stats','T_stats','wedge_stats','share_T_positive','share_wedge_positive','direction_reversal_share']},indent=2))
