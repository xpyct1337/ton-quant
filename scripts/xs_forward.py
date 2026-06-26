"""TON Quant - live paper forward-test of the cross-sectional momentum strategy.

Each run: (1) score the open basket if its 2-day hold has elapsed -> append realized
net spread to the live equity track record; (2) form the new point-in-time top-40
momentum baskets and log them. Builds out-of-sample evidence over calendar time -
the only cure for the single-bear-regime backtest caveat. PAPER ONLY, no orders.

Self-gating on elapsed time -> safe to schedule daily even though hold is 2 days.
conytail: reuse xs_momentum's universe/selection; state in two JSON files.
Run: python xs_forward.py   (schedule daily)
"""
import os, json, time, numpy as np, pandas as pd
import xs_momentum as xm

HOLD_MS=xm.H*4*3600*1000            # 2-day hold in ms
DATADIR=os.path.join(os.path.dirname(__file__),'..','data')
STATE=os.path.join(DATADIR,'xs_forward_state.json')
EQUITY=os.path.join(DATADIR,'xs_forward_equity.json')

def recent_panel(bars=140):
    """Fresh close+turnover panel for POOL (enough for M + turnover window)."""
    d={}
    for i in xm.POOL:
        try:
            df=xm.fetch(i,bars=bars)
            if len(df)>=xm.TURN_WIN+xm.M+5: d[i]=df
        except Exception: pass
    return xm.panels(d)

def current_baskets(C,V):
    """Point-in-time top-40 by trailing turnover at the latest CLOSED bar, then
    long top-quintile / short bottom-quintile by M-bar momentum."""
    t=len(C)-1                                   # latest fully-closed bar
    f=(C.iloc[t]/C.iloc[t-xm.M]-1)
    tt=V.rolling(xm.TURN_WIN).sum().iloc[t]
    ok=f.notna()&tt.notna()
    elig=list(tt[ok].sort_values().index[-xm.TOPN:])
    fv=f[elig].sort_values(); nq=max(3,int(len(elig)*xm.Q))
    short=list(fv.index[:nq]); long=list(fv.index[-nq:])
    px=C.iloc[t]
    return long, short, {n:float(px[n]) for n in long+short}, int(C.index[t])

def load(p,d): 
    return json.load(open(p)) if os.path.exists(p) else d
def save(p,o):
    os.makedirs(DATADIR,exist_ok=True); json.dump(o,open(p,'w'),indent=1)

def realized(open_pos,px_now):
    """Net spread return of the open basket marked at current prices."""
    def leg(names):
        r=[px_now[n]/open_pos['entry'][n]-1 for n in names if n in px_now and n in open_pos['entry']]
        return np.mean(r) if r else 0.0
    gross=leg(open_pos['long'])-leg(open_pos['short'])
    return gross-2*xm.FEE                          # full-turnover worst case per close

def main():
    C,V=recent_panel()
    long,short,entry,bar_ts=current_baskets(C,V)
    px_now={n:float(C.iloc[-1][n]) for n in C.columns}
    state=load(STATE,None); eq=load(EQUITY,{'records':[]})
    acted=False
    if state and bar_ts-state['bar_ts']>=HOLD_MS:        # hold elapsed -> close & score
        ret=realized(state,px_now)
        eq['records'].append({'open_ts':state['bar_ts'],'close_ts':bar_ts,'net':ret,
                              'long':state['long'],'short':state['short']})
        save(EQUITY,eq); acted=True
    if state is None or bar_ts-state['bar_ts']>=HOLD_MS:  # open a fresh basket
        save(STATE,{'bar_ts':bar_ts,'long':long,'short':short,'entry':entry})
        acted=True
    # report
    rets=[r['net'] for r in eq['records']]
    if rets:
        cum=np.prod([1+x for x in rets])-1
        sh=np.mean(rets)/np.std(rets)*np.sqrt(xm.HOLDS_PER_YEAR) if len(rets)>1 and np.std(rets)>0 else 0
        print(f"track: {len(rets)} closed holds | cum {cum*100:+.2f}% | annSharpe {sh:.2f} | last {rets[-1]*100:+.2f}%")
    print(f"{'REBALANCED' if acted else 'holding'} @ {pd.to_datetime(bar_ts,unit='ms')}")
    print(f"  LONG  ({len(long)}): {', '.join(n.split('-')[0] for n in long)}")
    print(f"  SHORT ({len(short)}): {', '.join(n.split('-')[0] for n in short)}")

if __name__=='__main__': main()
