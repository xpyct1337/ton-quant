#!/usr/bin/env python3
"""TON Quant — Alpha Engine stage 3: score signal types by forward outcomes.

Reads data/signals/*.json (journal) + data/snapshots/*.json (prices), computes
per-event returns at +1d/+3d/+7d and aggregates per signal type (n, win-rate,
avg, median). Pure recompute -> data/signals/scores.json, fully idempotent.
Run from repo root, stdlib only.
"""
import json, os, datetime, statistics

HORIZONS = (1, 3, 7)
MIN_N = 3          # verdicts need at least this many scored events
WR_EDGE = 55.0     # win-rate >= this AND avg>0 -> "edge"
WR_NOISE = 45.0    # win-rate < this OR avg<0 -> "noise"

def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default

def main():
    sidx = load("data/signals/index.json", {"dates": []})
    snap_dates = set(load("data/index.json", {"dates": []})["dates"])
    snaps = {}

    def price_at(date, addr):
        if date not in snap_dates:
            return None
        if date not in snaps:
            snaps[date] = load("data/snapshots/%s.json" % date, {"tokens": {}})["tokens"]
        t = snaps[date].get(addr)
        return t.get("price") if t else None

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
                ev["r%d" % h] = round((ph - p0) / p0 * 100, 2) if ph is not None else None
                scored = scored or ph is not None
            if scored:
                events.append(ev)

    per_sig = {}
    for sig in sorted({e["sig"] for e in events}):
        es = [e for e in events if e["sig"] == sig]
        agg = {}
        for h in HORIZONS:
            rs = [e["r%d" % h] for e in es if e.get("r%d" % h) is not None]
            agg["h%d" % h] = {
                "n": len(rs),
                "wr": round(100.0 * sum(1 for r in rs if r > 0) / len(rs), 1) if rs else None,
                "avg": round(sum(rs) / len(rs), 2) if rs else None,
                "med": round(statistics.median(rs), 2) if rs else None,
            }
        base_h = agg["h3"] if agg["h3"]["n"] else agg["h1"]
        if (base_h["n"] or 0) < MIN_N:
            agg["verdict"] = "collecting"
        elif base_h["wr"] >= WR_EDGE and base_h["avg"] > 0:
            agg["verdict"] = "edge"
        elif base_h["wr"] < WR_NOISE or base_h["avg"] < 0:
            agg["verdict"] = "noise"
        else:
            agg["verdict"] = "neutral"
        per_sig[sig] = agg

    out = {
        "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "horizons": list(HORIZONS), "min_n": MIN_N,
        "signal_days": len(sidx["dates"]), "events_scored": len(events),
        "per_sig": per_sig,
        # last 30 scored events, newest first — for the dashboard drill-down
        "recent": sorted(events, key=lambda e: e["date"], reverse=True)[:30],
    }
    os.makedirs("data/signals", exist_ok=True)
    with open("data/signals/scores.json", "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print("score: days=%d events=%d signals=%d" % (len(sidx["dates"]), len(events), len(per_sig)))

if __name__ == "__main__":
    main()
