"""TON Quant signal bot - walk-forward harness, triple-barrier labels, GBM meta.
Microstructure features (funding/OI/liquidations) from Coinalyze deep history.
Paper research only. Every printed number is out-of-sample.

Run: COINALYZE_KEY=... TQ_BAR=4H python signal_bot.py   (TQ_BAR=1D also works)
conytail: one file, one data dep added only after OKX funding proved too shallow.
"""
import os, time, pickle, numpy as np, pandas as pd, requests
from sklearn.ensemble import HistGradientBoostingClassifier

UNIVERSE=['BTC-USDT-SWAP','ETH-USDT-SWAP','SOL-USDT-SWAP','KSM-USDT-SWAP','DOGE-USDT-SWAP',
          'AVAX-USDT-SWAP','LINK-USDT-SWAP','LTC-USDT-SWAP','DOT-USDT-SWAP','ADA-USDT-SWAP']
BASE_FEATS=['rsi','z','atr_pct','dist200','relstr']
MICRO_FEATS=['funding','oi_chg','liq_long','liq_skew']
FEATS=BASE_FEATS+MICRO_FEATS
BAR=os.environ.get('TQ_BAR','4H'); BARS=3000 if BAR=='4H' else 1100
HOLD=30 if BAR=='4H' else 10
CZINT={'4H':'4hour','1D':'daily'}.get(BAR,'4hour')
CACHE=os.path.join(os.path.dirname(__file__),'okx_'+BAR+'.pkl')
CZCACHE=os.path.join(os.path.dirname(__file__),'coinalyze_'+BAR+'.pkl')
CZKEY=os.environ.get('COINALYZE_KEY','')

def fetch(inst,bars=BARS):
    out=[];after=''
    while len(out)<bars:
        p={'instId':inst,'bar':BAR,'limit':'100'}
        if after:p['after']=after
        d=requests.get('https://www.okx.com/api/v5/market/history-candles',params=p,timeout=15).json().get('data',[])
        if not d:break
        out+=d;after=d[-1][0];time.sleep(0.05)
    df=pd.DataFrame(out,columns=['ts','o','h','l','c','v','vc','vcq','cf']).iloc[::-1].reset_index(drop=True)
    for k in ['o','h','l','c']:df[k]=df[k].astype(float)
    df['ts']=df['ts'].astype(np.int64)
    return df[['ts','o','h','l','c']]

def load():
    if os.path.exists(CACHE): return pickle.load(open(CACHE,'rb'))
    d={i:fetch(i) for i in UNIVERSE}; pickle.dump(d,open(CACHE,'wb')); return d

def cz_symbol(o): return o.split('-')[0]+'USDT_PERP.A'   # .A = Binance perp on Coinalyze

def load_coinalyze(span_days=540):
    """Funding + open interest + liquidations per asset, 4h/daily. Cached.
    conytail: one call per endpoint (multi-symbol). Degrades to {} without a key."""
    if os.path.exists(CZCACHE): return pickle.load(open(CZCACHE,'rb'))
    if not CZKEY: return {}
    h={'api_key':CZKEY}; now=int(time.time()); frm=now-span_days*86400
    syms=','.join(cz_symbol(o) for o in UNIVERSE)
    def grab(ep):
        r=requests.get('https://api.coinalyze.net/v1/'+ep,headers=h,
            params={'symbols':syms,'interval':CZINT,'from':frm,'to':now},timeout=30)
        r.raise_for_status(); time.sleep(1.5)
        return {x['symbol']:x['history'] for x in r.json()}
    F=grab('funding-rate-history'); O=grab('open-interest-history'); L=grab('liquidation-history')
    out={}
    for o in UNIVERSE:
        s=cz_symbol(o); f=pd.DataFrame(F.get(s,[])); oi=pd.DataFrame(O.get(s,[])); lq=pd.DataFrame(L.get(s,[]))
        df=pd.DataFrame({'ts':(f['t']*1000).astype(np.int64),'funding':f['c'].astype(float)}) if len(f) else pd.DataFrame(columns=['ts','funding'])
        if len(oi): df=df.merge(pd.DataFrame({'ts':(oi['t']*1000).astype(np.int64),'oi':oi['c'].astype(float)}),on='ts',how='outer')
        if len(lq): df=df.merge(pd.DataFrame({'ts':(lq['t']*1000).astype(np.int64),'liq_l':lq['l'].astype(float),'liq_s':lq['s'].astype(float)}),on='ts',how='outer')
        out[o]=df.sort_values('ts').reset_index(drop=True)
    pickle.dump(out,open(CZCACHE,'wb')); return out

def cz_features(df, cz):
    """Align Coinalyze series to candle ts (backward) and derive features.
    conytail: merge_asof, no loop. All-NaN when data absent - HGB handles missing."""
    nan=lambda: np.full(len(df),np.nan)
    if cz is None or cz.empty or 'funding' not in cz: return {f:nan() for f in MICRO_FEATS}
    c=cz.dropna(subset=['ts']).sort_values('ts')
    m=pd.merge_asof(df[['ts']],c,on='ts',direction='backward')
    oi=m['oi'] if 'oi' in m else pd.Series(nan())
    ll=(m['liq_l'] if 'liq_l' in m else pd.Series(nan())).fillna(0)
    ls=(m['liq_s'] if 'liq_s' in m else pd.Series(nan())).fillna(0)
    return dict(funding=m['funding'].values,
                oi_chg=oi.pct_change(20).values,
                liq_long=(ll.rolling(6).sum()/oi).values,                        # long-liq flush vs OI (capitulation)
                liq_skew=((ll-ls).rolling(6).sum()/(ll+ls).rolling(6).sum().replace(0,np.nan)).values)

def rsi(s,n=14):
    d=s.diff();up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean();dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+up/dn)
def atr(df,n=14):
    pc=df['c'].shift();tr=pd.concat([df['h']-df['l'],(df['h']-pc).abs(),(df['l']-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n,adjust=False).mean()

def signals(df, btc_ret20, mx=None, tp=2.0, sl=1.0, hold=10):
    """Primary = pullback in uptrend. Triple-barrier (ATR TP/SL + time) label.
    conytail: primary is deliberately dumb/high-recall - the meta-model filters."""
    c=df['c'].values;h=df['h'].values;l=df['l'].values;ts=df['ts'].values
    if mx is None: mx={f:np.full(len(c),np.nan) for f in MICRO_FEATS}
    s=pd.Series(c)
    e200=s.ewm(span=200,adjust=False).mean().values
    e50=s.ewm(span=50,adjust=False).mean().values
    e20=s.ewm(span=20,adjust=False).mean().values
    rs=rsi(s).values; a=atr(df).values
    sma=s.rolling(20).mean().values; std=s.rolling(20).std().values
    ret20=s.pct_change(20).values
    rows=[]; i=200; N=len(c)
    while i<N-1:
        if c[i]>e200[i] and e50[i]>e200[i] and rs[i]<45 and c[i]<=e20[i] and a[i]>0:
            entry=c[i];tpx=entry+tp*a[i];slx=entry-sl*a[i];r=None;j=i
            for j in range(i+1,min(i+1+hold,N)):
                if l[j]<=slx:r=(slx-entry)/entry;break
                if h[j]>=tpx:r=(tpx-entry)/entry;break
            if r is None:r=(c[j]-entry)/entry
            row=dict(ts=ts[i], ret=r, win=int(r>0),
                rsi=rs[i], z=(c[i]-sma[i])/std[i] if std[i]>0 else 0,
                atr_pct=a[i]/c[i], dist200=(c[i]-e200[i])/c[i],
                relstr=(0 if np.isnan(ret20[i]) else ret20[i])-btc_ret20.get(ts[i],0.0))
            for f in MICRO_FEATS: row[f]=mx[f][i]
            rows.append(row); i=j+1
        else:i+=1
    return rows

def expectancy(r): r=np.array(r); return r.mean() if len(r) else 0.0
def pf(r):
    r=np.array(r); g=r[r>0].sum(); ls=-r[r<0].sum(); return g/ls if ls>0 else float('inf')

def build_signals():
    data=load(); cz=load_coinalyze()
    btc=data['BTC-USDT-SWAP']; bser=np.nan_to_num(pd.Series(btc['c'].values).pct_change(20).values)
    btc_ret20=dict(zip(btc['ts'].values, bser))
    rows=[]
    for inst,df in data.items():
        rows+=signals(df,btc_ret20,cz_features(df,cz.get(inst)),hold=HOLD)
    return pd.DataFrame(rows).sort_values('ts').reset_index(drop=True)

def walk_forward(d, folds=6, embargo=10):
    n=len(d); base=[]; meta=[]
    for k in range(1,folds):
        cut=int(n*k/folds); tr=d.iloc[:cut]; te=d.iloc[cut+embargo:int(n*(k+1)/folds)]
        if len(te)<5 or len(tr)<40: continue
        m=HistGradientBoostingClassifier(max_depth=3,max_iter=120,learning_rate=0.05,
            min_samples_leaf=15,l2_regularization=1.0).fit(tr[FEATS],tr.win)
        ptr=m.predict_proba(tr[FEATS])[:,1]
        thr=max(np.arange(0.3,0.7,0.05),
                key=lambda t: expectancy(tr.ret[ptr>=t]) if (ptr>=t).sum()>10 else -9)
        take=m.predict_proba(te[FEATS])[:,1]>=thr
        base+=list(te.ret); meta+=list(te.ret[take])
    return base, meta

def main():
    d=build_signals()
    assert d.ts.is_monotonic_increasing, "signals not time-sorted -> walk-forward would leak"
    assert ((d.win==1)==(d.ret>0)).all(), "label/return mismatch"
    cov=d['funding'].notna().mean()
    print("BAR=%s signals=%d  micro-coverage=%.0f%%"%(BAR,len(d),cov*100))
    base,meta=walk_forward(d)
    print("take-all : trades=%4d exp=%6.2f%% PF=%.2f"%(len(base),expectancy(base)*100,pf(base)))
    print("GBM meta : trades=%4d exp=%6.2f%% PF=%.2f"%(len(meta),expectancy(meta)*100,pf(meta)))
    print("EDGE" if expectancy(meta)>0 and len(meta)>=30 else
          "PROMISING but thin (meta trades < 30; confirm with more data)")

if __name__=='__main__':
    main()
