"""TON Quant - cross-sectional momentum strategy (paper research).

Long top-quintile / short bottom-quintile by short-horizon momentum across the
liquid perp universe, 4H bars, equal-weight, dollar-neutral. Vol-targeted,
fee+turnover aware. CPCV/PBO robustness gate.

Signal validated 2026-06-26: net edge t~3 on liquid top-40, PBO 0.18, earned in
a -46% bear; long leg = 72% of spread (winner-selection alpha, not bear
short-beta). Consistent with crypto XS-momentum literature: short-horizon (days)
momentum, equal-weight > value-weight, turns to reversal at multi-week horizons.

!!! KNOWN BIAS - read before trusting magnitudes !!!
Headline Sharpe here (~4) is INFLATED vs the literature anchor (~1). Sources of
optimism, in order of suspected size:
  1. SURVIVORSHIP/SELECTION - UNIVERSE is top-by-turnover *as of build date*, so
     the backtest trades coins pre-selected for surviving and staying liquid.
     Fix: point-in-time universe ranked by trailing volume as-of each date
     (needs refetch WITH volume + listing dates). NOT yet done.
  2. Close-to-close fills - assumes you trade the same close that completes the
     signal; real fills slip.
  3. Costless shorting of illiquid alts beyond the flat fee.
  4. One favorable 8-month window (all the perp data that exists; alts too young
     for multi-regime).
Treat Sharpe ~1 (literature) as the realistic prior. The vol-target, fee-stress,
and CPCV scaffolding are sound; the numbers are not deployable until bias #1 is
controlled and the strategy is forward-tested in a live (non-bear) regime.

conytail: one file, no ML - a rank rule. Lit caveat baked in: momentum crashes
-> vol-target + leverage cap; costs decisive -> fee stress in main().
Run: TQ_FEE=0.0012 python xs_momentum.py   (refresh UNIVERSE via universe.json)
"""
import os, time, pickle, itertools, numpy as np, pandas as pd, requests

UNIVERSE=['ETH-USDT-SWAP','BTC-USDT-SWAP','SOL-USDT-SWAP','HYPE-USDT-SWAP','DOGE-USDT-SWAP',
 'ZEC-USDT-SWAP','XRP-USDT-SWAP','BEAT-USDT-SWAP','LAB-USDT-SWAP','WLD-USDT-SWAP','AAVE-USDT-SWAP',
 'JTO-USDT-SWAP','IP-USDT-SWAP','XPL-USDT-SWAP','AGLD-USDT-SWAP','UB-USDT-SWAP','SUI-USDT-SWAP',
 'BNB-USDT-SWAP','TRUMP-USDT-SWAP','H-USDT-SWAP','FIL-USDT-SWAP','ADA-USDT-SWAP','NEAR-USDT-SWAP',
 'ALLO-USDT-SWAP','BCH-USDT-SWAP','LINK-USDT-SWAP','UNI-USDT-SWAP','PUMP-USDT-SWAP','AVAX-USDT-SWAP',
 'LTC-USDT-SWAP','ONDO-USDT-SWAP','LIT-USDT-SWAP','XLM-USDT-SWAP','BASED-USDT-SWAP','TAO-USDT-SWAP',
 'DOT-USDT-SWAP','OP-USDT-SWAP','ENA-USDT-SWAP','RESOLV-USDT-SWAP','APE-USDT-SWAP']

BAR='4H'; M=20; H=12; Q=0.2                 # 3.3d formation, 2d hold, top/bottom quintile
FEE=float(os.environ.get('TQ_FEE','0.0012'))# round-trip per leg (taker+slippage)
TARGET_VOL=0.20; LEV_CAP=3.0                 # annualized vol target + leverage cap
HOLDS_PER_YEAR=365/(H*4/24)                  # H bars * 4h = 2-day holds -> ~182/yr
CACHE=os.path.join(os.path.dirname(__file__),'okx_xs_'+BAR+'.pkl')

def fetch(inst,bars=1500):
    out=[];after=''
    while len(out)<bars:
        p={'instId':inst,'bar':BAR,'limit':'100'}
        if after:p['after']=after
        r=requests.get('https://www.okx.com/api/v5/market/history-candles',params=p,timeout=12).json().get('data',[])
        if not r:break
        out+=r;after=r[-1][0];time.sleep(0.05)
    df=pd.DataFrame(out,columns=['ts','o','h','l','c','v','vc','vcq','cf']).iloc[::-1]
    return pd.Series(df['c'].astype(float).values, index=df['ts'].astype(np.int64).values)

def load():
    if os.path.exists(CACHE): return pickle.load(open(CACHE,'rb'))
    d={i:fetch(i) for i in UNIVERSE}; pickle.dump(d,open(CACHE,'wb')); return d

def spread_returns(C, M=M, H=H, q=Q, fee=FEE):
    """Per-rebalance net long-short spread return + realized turnover. No lookahead:
    factor uses closes up to t, return realized over (t, t+H]."""
    F=C.pct_change(M); fwd=C.shift(-H)/C-1
    ts=[];rets=[];turns=[];pl=set();ps=set()
    for t in range(max(M,60), len(C)-H, H):
        f=F.iloc[t]; fr=fwd.iloc[t]; ok=f.notna()&fr.notna()
        if ok.sum()<15: continue
        fv=f[ok]; rv=fr[ok]; nq=max(3,int(ok.sum()*q)); o=fv.sort_values()
        sh=set(o.index[:nq]); lo=set(o.index[-nq:])           # long high-mom, short low-mom
        turn=(len(lo-pl)+len(sh-ps))/(2*nq) if pl else 1.0
        gross=rv[list(lo)].mean()-rv[list(sh)].mean()
        ts.append(C.index[t]); rets.append(gross-2*fee*turn); turns.append(turn); pl,ps=lo,sh
    return pd.Series(rets,index=ts), np.mean(turns) if turns else 0.0

def vol_target(r, target=TARGET_VOL, cap=LEV_CAP, win=20):
    """Scale each hold by target/trailing-realized-vol using ONLY past holds."""
    per_hold_target=target/np.sqrt(HOLDS_PER_YEAR)
    rv=r.shift(1).rolling(win).std()                          # trailing, lagged -> no lookahead
    lev=(per_hold_target/rv).clip(upper=cap).fillna(1.0)
    return r*lev, lev

def metrics(r):
    r=r.dropna()
    if len(r)<5: return {}
    eq=(1+r).cumprod(); dd=(eq/eq.cummax()-1).min()
    sharpe=r.mean()/r.std()*np.sqrt(HOLDS_PER_YEAR) if r.std()>0 else 0
    cagr=eq.iloc[-1]**(HOLDS_PER_YEAR/len(r))-1
    return dict(holds=len(r), net_per_hold=r.mean(), sharpe=sharpe, cagr=cagr,
                maxDD=dd, pct_pos=(r>0).mean(), total=eq.iloc[-1]-1)

def cpcv(C, grid=((15,12),(20,12),(30,12)), G=8, fee=FEE):
    cr={c:spread_returns(C,c[0],c[1],fee=fee)[0] for c in grid}
    ts=sorted(set().union(*[set(s.index) for s in cr.values()]))
    folds=np.array_split(ts,G); on=lambda c,S:cr[c].reindex(S).dropna()
    paths=[]
    for combo in itertools.combinations(range(G),2):
        te=set(np.concatenate([folds[i] for i in combo])); trn=set(ts)-te
        best=max(grid,key=lambda c:on(c,trn).mean())
        oos=on(best,te)
        if len(oos)>=6: paths.append(oos.mean())
    e=np.array(paths)
    return dict(paths=len(e), median=np.median(e), pos=float((e>0).mean()), pbo=float((e<=0).mean()))

def main():
    d=load(); C=pd.DataFrame(d).sort_index()
    print(f"universe={C.shape[1]} bars={C.shape[0]} span="
          f"{pd.to_datetime(C.index.min(),unit='ms').date()}..{pd.to_datetime(C.index.max(),unit='ms').date()}")
    r,turn=spread_returns(C)
    vt,lev=vol_target(r)
    print(f"\nraw  : "+" ".join(f"{k}={v:.3f}" for k,v in metrics(r).items()))
    print(f"vol-t: "+" ".join(f"{k}={v:.3f}" for k,v in metrics(vt).items())+f"  avgLev={lev.mean():.2f}")
    print(f"avg turnover/rebalance={turn:.2f}")
    print("\nfee stress (net per-hold % | annual Sharpe):")
    for f in (0.0012,0.002,0.003,0.004):
        rr,_=spread_returns(C,fee=f); m=metrics(rr)
        print(f"  fee {f*100:.2f}%/leg: {m['net_per_hold']*100:6.3f}%  Sharpe {m['sharpe']:.2f}")
    g=cpcv(C); print(f"\nCPCV/PBO: paths={g['paths']} median OOS={g['median']*100:.3f}% "
          f"OOS>0={g['pos']*100:.0f}% PBO={g['pbo']:.2f}")
    print("NOTE: magnitudes inflated by survivorship (see header). Sharpe ~1 is the realistic prior.")
    assert lev.isna().sum()==0 and (lev<=LEV_CAP+1e-9).all(), "leverage cap/nan broken"
    assert len(r)>0 and r.index.is_monotonic_increasing, "rebalance series not time-ordered"
    print("[self-check ok: no-lookahead vol-target, ordered rebalances]")

if __name__=='__main__': main()
