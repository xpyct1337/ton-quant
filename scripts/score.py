#!/usr/bin/env python3
"""TON Quant — Alpha Engine stage 3: score signal types by forward outcomes.

Reads data/signals/*.json (journal) + data/snapshots/*.json (prices), computes
per-event forward returns at +1d/+3d/+7d, MARKET-RELATIVE (excess) returns vs
the tradeable basket, and aggregates per signal type with statistical rigor:
  - absolute win-rate / avg / median (kept for the dashboard, backward compat)
  - excess (market-adjusted) win-rate / avg / median   <- the real alpha test
  - Wilson 95% lower bound on the excess win-rate        <- "better than a coin?"
  - two-sided sign-test p-value on excess wins           <- significance
  - walk-forward: in-sample verdict vs out-of-sample confirmation

Pure recompute -> data/signals/scores.json, fully idempotent.
Run from repo root, stdlib only. Stat helpers are importable + self-tested
(see scripts/score_test.py).

Why excess returns: when the whole market trends down (TON + most jettons red),
absolute returns brand every signal "noise". A signal has edge only if it beats
just holding the basket, so we measure return MINUS the universe mean return over
the same horizon. Verdict "edge" now requires the excess win-rate to be
statistically above 50% (Wilson lo > 50), not merely a lucky point estimate.
"""
import json, os, datetime, statistics, math

HORIZONS = (1, 3, 7)
MIN_N = 3            # verdicts need at least this many scored events
MIN_OOS = 2          # walk-forward needs this many out-of-sample events
Z = 1.96             # 95% normal quantile for Wilson interval
EXCLUDE_CATS = {"stable", "staking"}   # not tradeable alpha universe


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


# ---------- pure, importable, self-tested statistics ----------
def wilson_lo(wins, n, z=Z):
    """Lower bound of the Wilson score interval for a proportion, in %.
    Returns None if n==0. Conservative estimate of the true win-rate."""
    if not n:
        return None
    p = wins / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round(max(0.0, (center - margin) / denom) * 100, 1)


def sign_test_p(wins, losses):
    """Two-sided exact binomial (sign) test p-value vs fair coin (p=0.5),
    ignoring ties. Returns None if no decisive events. p near 0 => significant."""
    n = wins + losses
    if n == 0:
        return None
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return round(min(1.0, 2 * tail), 4)


def agg_returns(rs):
    """Aggregate a list of return %s -> dict(n, wr, avg, med)."""
    if not rs:
        return {"n": 0, "wr": None, "avg": None, "med": None}
    return {
        "n": len(rs),
        "wr": round(100.0 * sum(1 for r in rs if r > 0) / len(rs), 1),
        "avg": round(sum(rs) / len(rs), 2),
        "med": round(statistics.median(rs), 2),
    }


def classify(excess_rs, min_n=MIN_N):
    """Verdict from a list of EXCESS returns using significance, not luck.
      collecting : < min_n events
      edge       : avg excess > 0 AND Wilson lo win-rate > 50%
      noise      : win-rate < 45% OR avg excess < 0
      neutral    : otherwise (positive but not yet significant)
    Returns (verdict, wilson_lo, sign_p)."""
    n = len(excess_rs)
    wins = sum(1 for r in excess_rs if r > 0)
    losses = sum(1 for r in excess_rs if r < 0)
    lo = wilson_lo(wins, n)
    p = sign_test_p(wins, losses)
    if n < min_n:
        return "collecting", lo, p
    avg = sum(excess_rs) / n
    wr = 100.0 * wins / n
    if avg > 0 and lo is not None and lo > 50.0:
        return "edge", lo, p
    if wr < 45.0 or avg < 0:
        return "noise", lo, p
    return "neutral", lo, p


def main():
    sidx = load("data/signals/index.json", {"dates": []})
    snap_meta = load("data/index.json", {"dates": []})
    snap_dates = set(snap_meta.get("dates", []))
    cats = load("data/cats.json", {})
    snaps = {}

    def tokens_on(date):
        if date not in snap_dates:
            return {}
        if date not in snaps:
            snaps[date] = load("data/snapshots/%s.json" % date, {"tokens": {}})["tokens"]
        return snaps[date]

    def price_at(date, addr):
        t = tokens_on(date).get(addr)
        return t.get("price") if t else None

    mkt_cache = {}

    def market_ret(date, h):
        key = (date, h)
        if key in mkt_cache:
            return mkt_cache[key]
        d2 = (datetime.date.fromisoformat(date) + datetime.timedelta(days=h)).isoformat()
        toks0, toks1 = tokens_on(date), tokens_on(d2)
        rets = []
        for a, t0 in toks0.items():
            if cats.get(a, "meme") in EXCLUDE_CATS:
                continue
            p0 = t0.get("price")
            t1 = toks1.get(a)
            p1 = t1.get("price") if t1 else None
            if p0 and p1:
                rets.append((p1 - p0) / p0 * 100)
        val = round(sum(rets) / len(rets), 4) if rets else None
        mkt_cache[key] = val
        return val

    events = []
    for d in sidx["dates"]:
        day = load("data/signals/%s.json" % d, None)
        if not day:
            continue
        base = datetime.date.fromisoformat(d)
        for s in day.get("signals", []):
            p0 = s.get("price")
            if not p0:
                continue
            ev = {"date": d, "addr": s["addr"], "sym": s.get("sym"),
                  "sig": s["sig"], "w": s.get("w")}
            scored = False
            for h in HORIZONS:
                ph = price_at((base + datetime.timedelta(days=h)).isoformat(), s["addr"])
                if ph is not None:
                    r = (ph - p0) / p0 * 100
                    ev["r%d" % h] = round(r, 2)
                    mr = market_ret(d, h)
                    ev["x%d" % h] = round(r - mr, 2) if mr is not None else None
                    scored = True
                else:
                    ev["r%d" % h] = None
                    ev["x%d" % h] = None
            if scored:
                events.append(ev)

    sdates = sorted({e["date"] for e in events})
    split = sdates[len(sdates) // 2] if sdates else None

    per_sig = {}
    for sig in sorted({e["sig"] for e in events}):
        es = [e for e in events if e["sig"] == sig]
        agg = {}
        for h in HORIZONS:
            agg["h%d" % h] = agg_returns([e["r%d" % h] for e in es if e.get("r%d" % h) is not None])
        xagg = {}
        for h in HORIZONS:
            xagg["h%d" % h] = agg_returns([e["x%d" % h] for e in es if e.get("x%d" % h) is not None])
        agg["x"] = xagg
        h3x = [e["x3"] for e in es if e.get("x3") is not None]
        base_x = h3x if len(h3x) >= MIN_N else [e["x1"] for e in es if e.get("x1") is not None]
        verdict, lo, p = classify(base_x)
        agg["verdict"], agg["sig_lo"], agg["p"] = verdict, lo, p
        agg["base_h"] = 3 if len(h3x) >= MIN_N else 1
        if split is not None:
            ins = [e["x1"] for e in es if e["date"] < split and e.get("x1") is not None]
            oos = [e["x1"] for e in es if e["date"] >= split and e.get("x1") is not None]
            ins_avg = round(sum(ins) / len(ins), 2) if ins else None
            oos_avg = round(sum(oos) / len(oos), 2) if oos else None
            confirmed = (ins_avg is not None and oos_avg is not None
                         and len(oos) >= MIN_OOS and ins_avg > 0 and oos_avg > 0)
            agg["wf"] = {"split": split, "ins_n": len(ins), "ins_avg": ins_avg,
                         "oos_n": len(oos), "oos_avg": oos_avg, "confirmed": confirmed}
        per_sig[sig] = agg

    out = {
        "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "horizons": list(HORIZONS), "min_n": MIN_N, "method": "excess+wilson+walkfwd",
        "split": split,
        "signal_days": len(sidx["dates"]), "events_scored": len(events),
        "per_sig": per_sig,
        "recent": sorted(events, key=lambda e: e["date"], reverse=True)[:30],
    }
    os.makedirs("data/signals", exist_ok=True)
    with open("data/signals/scores.json", "w") as f:
        json.dump(out, f, separators=(",", ":"))
    edges = [s for s, a in per_sig.items() if a["verdict"] == "edge"]
    print("score: days=%d events=%d signals=%d split=%s edges=%s"
          % (len(sidx["dates"]), len(events), len(per_sig), split, edges or "none"))


if __name__ == "__main__":
    main()
