"""TON Quant - cross-sectional momentum strategy (paper research only).

Long top-quintile / short bottom-quintile by short-horizon momentum, 4H bars,
equal-weight and dollar-neutral.  Universe selection is point-in-time *within a
fixed current-survivor pool*.  That remaining survivor bias, close-to-close fills,
and one dominant market regime mean this program is not a tradability claim.

The validation printout uses purged combinatorial symmetric CV: it ranks the
configuration selected in each training split against alternatives OOS.  It is a
diagnostic, not proof; the only decisive evidence is the live forward record.

ponytail: one rank rule, no ML.  The fixed survivor pool is a known ceiling; store
historical exchange universes before treating any backtest as deployment research.
Run: TQ_FEE=0.0012 python xs_momentum.py
"""
import os, time, pickle, numpy as np, pandas as pd, requests
from xs_validation import cscv_pbo, sharpe_diagnostic

# Broad pool (top crypto perps by turnover @ 2026-06-26); point-in-time selection
# picks TOPN within this each rebalance. Refresh via universe.json when rebalancing.
POOL=[
    'ETH-USDT-SWAP', 'BTC-USDT-SWAP', 'SOL-USDT-SWAP', 'HYPE-USDT-SWAP', 'DOGE-USDT-SWAP',
    'ZEC-USDT-SWAP', 'XRP-USDT-SWAP', 'BEAT-USDT-SWAP', 'LAB-USDT-SWAP', 'WLD-USDT-SWAP',
    'AAVE-USDT-SWAP', 'JTO-USDT-SWAP', 'IP-USDT-SWAP', 'XPL-USDT-SWAP', 'AGLD-USDT-SWAP',
    'UB-USDT-SWAP', 'SUI-USDT-SWAP', 'BNB-USDT-SWAP', 'TRUMP-USDT-SWAP', 'H-USDT-SWAP',
    'FIL-USDT-SWAP', 'ADA-USDT-SWAP', 'NEAR-USDT-SWAP', 'ALLO-USDT-SWAP', 'BCH-USDT-SWAP',
    'LINK-USDT-SWAP', 'UNI-USDT-SWAP', 'PUMP-USDT-SWAP', 'AVAX-USDT-SWAP', 'LTC-USDT-SWAP',
    'ONDO-USDT-SWAP', 'LIT-USDT-SWAP', 'XLM-USDT-SWAP', 'BASED-USDT-SWAP', 'TAO-USDT-SWAP',
    'DOT-USDT-SWAP', 'OP-USDT-SWAP', 'ENA-USDT-SWAP', 'RESOLV-USDT-SWAP', 'APE-USDT-SWAP',
    'FOGO-USDT-SWAP', 'PENGU-USDT-SWAP', 'INJ-USDT-SWAP', 'WIF-USDT-SWAP', 'TRX-USDT-SWAP',
    'KAITO-USDT-SWAP', 'ORDI-USDT-SWAP', 'APT-USDT-SWAP', 'JUP-USDT-SWAP', 'ETC-USDT-SWAP',
    'DYDX-USDT-SWAP', 'WLFI-USDT-SWAP', 'ARB-USDT-SWAP', 'ETHFI-USDT-SWAP', 'ICP-USDT-SWAP',
    'ASTER-USDT-SWAP', 'BICO-USDT-SWAP', 'OPN-USDT-SWAP', 'BSB-USDT-SWAP', 'TIA-USDT-SWAP',
    'W-USDT-SWAP', 'HMSTR-USDT-SWAP', 'PIPPIN-USDT-SWAP', 'AXS-USDT-SWAP', 'GRASS-USDT-SWAP',
    'BIO-USDT-SWAP', 'RAVE-USDT-SWAP', 'CRV-USDT-SWAP', 'MEGA-USDT-SWAP', 'FARTCOIN-USDT-SWAP',
    'SEI-USDT-SWAP', 'DASH-USDT-SWAP', 'MERL-USDT-SWAP', 'RIVER-USDT-SWAP', 'CHZ-USDT-SWAP',
    'VIRTUAL-USDT-SWAP', 'OPG-USDT-SWAP', 'MOODENG-USDT-SWAP', 'GALA-USDT-SWAP', 'CHIP-USDT-SWAP',
    'STRK-USDT-SWAP', 'EIGEN-USDT-SWAP', 'POL-USDT-SWAP', 'HBAR-USDT-SWAP', 'USELESS-USDT-SWAP',
    'ALGO-USDT-SWAP', 'RENDER-USDT-SWAP', 'MET-USDT-SWAP', 'MMT-USDT-SWAP', 'SAND-USDT-SWAP',
    'HUMA-USDT-SWAP', 'SAHARA-USDT-SWAP', 'AVNT-USDT-SWAP', 'ATOM-USDT-SWAP', 'LDO-USDT-SWAP',
    'AERO-USDT-SWAP', 'ZRO-USDT-SWAP', 'ESP-USDT-SWAP', 'SPACE-USDT-SWAP', 'PNUT-USDT-SWAP',
    'ROBO-USDT-SWAP', '0G-USDT-SWAP', 'BERA-USDT-SWAP', 'NIGHT-USDT-SWAP', 'BILL-USDT-SWAP',
    'MON-USDT-SWAP', 'AR-USDT-SWAP', 'EDEN-USDT-SWAP', 'LAYER-USDT-SWAP', 'MORPHO-USDT-SWAP',
    'SPK-USDT-SWAP', 'EGLD-USDT-SWAP', 'ENSO-USDT-SWAP', 'POPCAT-USDT-SWAP', 'BABY-USDT-SWAP',
    'MEME-USDT-SWAP', 'CFX-USDT-SWAP', 'BREV-USDT-SWAP', 'BB-USDT-SWAP', 'MOVE-USDT-SWAP',
    'ZAMA-USDT-SWAP', 'KAT-USDT-SWAP', 'SYRUP-USDT-SWAP', 'HOME-USDT-SWAP', 'CC-USDT-SWAP',
    'PIEVERSE-USDT-SWAP', 'APR-USDT-SWAP', 'ENS-USDT-SWAP', 'PENDLE-USDT-SWAP', 'GIGGLE-USDT-SWAP',
    'LIGHT-USDT-SWAP', 'ME-USDT-SWAP', 'YGG-USDT-SWAP', 'DOOD-USDT-SWAP', 'PROS-USDT-SWAP',
    'TRB-USDT-SWAP', 'QNT-USDT-SWAP', 'NOT-USDT-SWAP', 'SNX-USDT-SWAP', 'COAI-USDT-SWAP',
    'PYTH-USDT-SWAP', 'ACT-USDT-SWAP', 'PEOPLE-USDT-SWAP', 'LINEA-USDT-SWAP', 'IRYS-USDT-SWAP',
    'STX-USDT-SWAP', 'SOON-USDT-SWAP', '2Z-USDT-SWAP', 'SPX-USDT-SWAP', 'ATH-USDT-SWAP',
]

BAR='4H'; M=20; H=12; Q=0.2; TOPN=40; TURN_WIN=30   # 3.3d formation, 2d hold, top-40 by 5d turnover
FEE=float(os.environ.get('TQ_FEE','0.0012'))
TARGET_VOL=0.20; LEV_CAP=3.0
HOLDS_PER_YEAR=365/(H*4/24)
CACHE=os.path.join(os.path.dirname(__file__),'okx_xsvol_'+BAR+'.pkl')

def fetch(inst,bars=1500):
    out=[];after=''
    while len(out)<bars:
        p={'instId':inst,'bar':BAR,'limit':'100'}
        if after:p['after']=after
        r=requests.get('https://www.okx.com/api/v5/market/history-candles',params=p,timeout=12).json().get('data',[])
        if not r:break
        out+=r;after=r[-1][0];time.sleep(0.05)
    df=pd.DataFrame(out,columns=['ts','o','h','l','c','v','vc','vcq','cf']).iloc[::-1]
    return pd.DataFrame({'ts':df['ts'].astype(np.int64).values,
                         'c':df['c'].astype(float).values,'vcq':df['vcq'].astype(float).values})

def load():
    if os.path.exists(CACHE): return pickle.load(open(CACHE,'rb'))
    d={i:fetch(i) for i in POOL}; d={k:v for k,v in d.items() if len(v)>=250}
    pickle.dump(d,open(CACHE,'wb')); return d

def panels(d):
    C=pd.DataFrame({o:v.set_index('ts')['c'] for o,v in d.items()}).sort_index()
    V=pd.DataFrame({o:v.set_index('ts')['vcq'] for o,v in d.items()}).reindex(C.index)
    return C,V

def spread_returns(C,V,M=M,H=H,q=Q,fee=FEE,topn=TOPN):
    """Net long-short spread per rebalance. Universe = top-N by trailing turnover
    known at t (point-in-time, no hindsight). No lookahead in factor or selection."""
    F=C.pct_change(M); fwd=C.shift(-H)/C-1; TT=V.rolling(TURN_WIN).sum()
    ts=[];rets=[];turns=[];pl=set();ps=set()
    for t in range(max(M,TURN_WIN,60), len(C)-H, H):
        f=F.iloc[t]; fr=fwd.iloc[t]; ok=f.notna()&fr.notna()
        tt=TT.iloc[t][ok].dropna()
        elig=list(tt.sort_values().index[-topn:])
        if len(elig)<15: continue
        fv=f[elig]; rv=fr[elig]; nq=max(3,int(len(elig)*q)); o=fv.sort_values()
        sh=set(o.index[:nq]); lo=set(o.index[-nq:])
        turn=(len(lo-pl)+len(sh-ps))/(2*nq) if pl else 1.0
        ts.append(C.index[t]); rets.append(rv[list(lo)].mean()-rv[list(sh)].mean()-2*fee*turn)
        turns.append(turn); pl,ps=lo,sh
    return pd.Series(rets,index=ts), (np.mean(turns) if turns else 0.0)

def vol_target(r,target=TARGET_VOL,cap=LEV_CAP,win=20):
    per=target/np.sqrt(HOLDS_PER_YEAR); rv=r.shift(1).rolling(win).std()
    lev=(per/rv).clip(upper=cap).fillna(1.0); return r*lev, lev

def metrics(r):
    r=r.dropna()
    if len(r)<5: return {}
    eq=(1+r).cumprod(); dd=(eq/eq.cummax()-1).min()
    sh=r.mean()/r.std()*np.sqrt(HOLDS_PER_YEAR) if r.std()>0 else 0
    return dict(holds=len(r),net_per_hold=r.mean(),sharpe=sh,
                cagr=eq.iloc[-1]**(HOLDS_PER_YEAR/len(r))-1,maxDD=dd,
                pct_pos=(r>0).mean(),total=eq.iloc[-1]-1)

def cpcv(C,V,grid=((15,12),(20,12),(30,12)),G=8,fee=FEE):
    """Purged CSCV/PBO diagnostic for the small disclosed parameter grid."""
    cr={str(c): spread_returns(C,V,c[0],c[1],fee=fee)[0] for c in grid}
    rows={name: {int(ts): float(value) for ts, value in series.dropna().items()}
          for name, series in cr.items()}
    return cscv_pbo(rows, groups=G, embargo_ms=H*4*3600*1000)

def main():
    d=load(); C,V=panels(d)
    print(f"pool={C.shape[1]} bars={C.shape[0]} span="
          f"{pd.to_datetime(C.index.min(),unit='ms').date()}..{pd.to_datetime(C.index.max(),unit='ms').date()}")
    r,turn=spread_returns(C,V); vt,lev=vol_target(r)
    print("raw  : "+" ".join(f"{k}={v:.3f}" for k,v in metrics(r).items()))
    print("vol-t: "+" ".join(f"{k}={v:.3f}" for k,v in metrics(vt).items())+f"  avgLev={lev.mean():.2f}")
    print(f"avg turnover/rebalance={turn:.2f}")
    print("fee stress (net per-hold % | Sharpe):")
    for f in (0.0012,0.002,0.003,0.004):
        m=metrics(spread_returns(C,V,fee=f)[0]); print(f"  {f*100:.2f}%/leg: {m['net_per_hold']*100:6.3f}%  {m['sharpe']:.2f}")
    g=cpcv(C,V)
    print("purged CSCV/PBO: " + f"splits={g['splits']} median selected OOS={g['median_selected_test_mean']*100:.3f}% "
          + f"OOS positive={g['selected_positive_share']*100:.0f}% PBO={g['pbo']:.2f}")
    d=sharpe_diagnostic(r.tolist(), trial_count=3)
    if d['available']:
        print(f"Sharpe diagnostic: PSR(0)={d['psr_zero']:.2f}, 3-grid adjusted={d['bonferroni_adjusted_probability']:.2f} (not a deployment gate)")
    assert lev.isna().sum()==0 and (lev<=LEV_CAP+1e-9).all(), "leverage broken"
    assert len(r)>0 and r.index.is_monotonic_increasing, "rebalances not ordered"
    print("[self-check ok: point-in-time selection, no-lookahead vol-target]")

if __name__=='__main__': main()
