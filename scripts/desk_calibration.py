#!/usr/bin/env python3
"""TON Quant v3.0 — desk self-calibration (deterministic fitness function).

Measures whether the desk's manipulation signal predicts bad forward outcomes,
using ONLY data the pipeline already collects (dated snapshots + wash_ban dates).
No LLM, no new fetches — cheap and reproducible (good for the passively-cooled Air).

(a) feature backtest: across data/snapshots/*, bucket every token by its as-of
    deterministic floor risk (desk.floor_risk on desk_features) and measure mean
    forward EXCESS return at +1/+3/+7d. Hypothesis: high < med < low.
(b) verdict scoring: for journaled data/desk/verdicts/<date>.json whose +7d window
    elapsed, score token manip_risk vs realized forward excess return.

Run from repo root.  Self-check:  python3 scripts/desk_calibration.py --check
"""
import json, os, sys, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_features import load, vol_auth, conc, load_aux, load_snaps, forward_excess  # noqa: E402
from desk import floor_risk                      # noqa: E402

HORIZONS = (1, 3, 7)
BUNDLE_THRESHOLD = 0.2
BUNDLE_MIN_N = 10


def banned_as_of(wash_ban, addr, date):
    bd = wash_ban.get(addr)
    return bool(bd and bd <= date)


def bucket_means(rows):
    """rows: list of (risk, excess). -> {risk: {n, avg}} for low/med/high."""
    acc = {b: [] for b in ("low", "med", "high")}
    for risk, ex in rows:
        if risk in acc and ex is not None:
            acc[risk].append(ex)
    return {b: {"n": len(xs), "avg": (sum(xs) / len(xs) if xs else 0.0)}
            for b, xs in acc.items()}


def monotonic_separation(buckets):
    """Require the stated risk ordering high < med < low, not just endpoints."""
    if any(buckets.get(b, {}).get("n", 0) == 0 for b in ("low", "med", "high")):
        return False
    return (buckets["high"]["avg"] < buckets["med"]["avg"]
            < buckets["low"]["avg"])


def bundle_backtest(snaps, aux=None, horizon=7):
    """Compare existing forensics bundle flag with later excess returns."""
    aux = load_aux() if aux is None else aux
    rows = []
    for date, tokens in aux.items():
        for addr, feat in (tokens or {}).items():
            bundle = feat.get("bundle")
            ex = forward_excess(snaps, date, addr, horizon) if bundle is not None else None
            if ex is not None:
                rows.append((bundle >= BUNDLE_THRESHOLD, ex))
    high = [ex for flagged, ex in rows if flagged]
    low = [ex for flagged, ex in rows if not flagged]
    missing = []
    if len(high) < BUNDLE_MIN_N:
        missing.append("high_n>=10")
    if len(low) < BUNDLE_MIN_N:
        missing.append("low_n>=10")
    # ponytail: fixed 10-observation floor keeps this diagnostic descriptive;
    # replace with a confidence-bounded gate after the panel grows.
    bucket = lambda xs: {"n": len(xs), "avg": round(sum(xs) / len(xs), 4) if xs else None}
    return {
        "feature": "bundle",
        "threshold": BUNDLE_THRESHOLD,
        "horizon": horizon,
        "available": not missing,
        "missing": missing,
        "high": bucket(high),
        "low": bucket(low),
        "candidate": not missing and bool(high) and bool(low) and sum(high) / len(high) < sum(low) / len(low),
    }


def feature_backtest(snaps, wash_ban):
    """Deterministic risk bucket vs forward excess return, per horizon."""
    by_h = {}
    for k in HORIZONS:
        rows = []
        for date in snaps:
            for addr, t in (snaps[date].get("tokens", {}) or {}).items():
                feat = {"wash": 1.0 if banned_as_of(wash_ban, addr, date) else 0.0,
                        "vol_auth": vol_auth(t), "conc": conc(t), "co_entry": 0.0}
                risk, _ = floor_risk(feat)
                ex = forward_excess(snaps, date, addr, k)
                if ex is not None:
                    rows.append((risk, ex))
        by_h[f"+{k}d"] = bucket_means(rows)
    return by_h


def verdict_scoring(snaps):
    """Score matured journaled token verdicts vs realized +7d forward excess."""
    idx = (load("data/index.json", {}) or {}).get("tokens", {})   # addr -> sym
    sym2addr = {}
    for a, s in idx.items():
        sym2addr.setdefault(s, a)
    scored = {b: [] for b in ("low", "med", "high")}
    for f in sorted(glob.glob("data/desk/verdicts/*.json")):
        date = os.path.basename(f)[:-5]
        v = load(f, {})
        for t in v.get("tokens", []):
            addr = sym2addr.get(t.get("sym"))
            if not addr:
                continue
            ex = forward_excess(snaps, date, addr, 7)
            if ex is not None and t.get("manip_risk") in scored:
                scored[t["manip_risk"]].append(ex)
    return {b: {"n": len(xs), "avg": (sum(xs) / len(xs) if xs else 0.0)}
            for b, xs in scored.items()}


def build_calibration():
    snaps = load_snaps()
    wash_ban = (load("data/paper/bots.json", {}) or {}).get("wash_ban", {})
    bt = feature_backtest(snaps, wash_ban)
    vs = verdict_scoring(snaps)
    h7 = bt.get("+7d", {})                       # do high-risk tokens underperform low?
    pairwise = (h7.get("high", {}).get("n", 0) > 0
                and h7.get("low", {}).get("n", 0) > 0
                and h7["high"]["avg"] < h7["low"]["avg"])
    return {"snapshots": len(snaps), "feature_backtest": bt,
            "verdict_scoring": vs,
            "bundle_backtest": bundle_backtest(snaps),
            "signal_separates_at_7d": monotonic_separation(h7),
            "signal_high_vs_low_at_7d": pairwise}


def main():
    cal = build_calibration()
    os.makedirs("data/desk", exist_ok=True)
    with open("data/desk/calibration.json", "w") as f:
        json.dump(cal, f, ensure_ascii=False, indent=2)
    chk = json.load(open("data/desk/calibration.json"))  # read-back
    h7 = chk["feature_backtest"].get("+7d", {})
    print(f"calibration: {chk['snapshots']} snapshots | +7d avg excess "
          f"low={h7.get('low', {}).get('avg', 0):+.3f} "
          f"med={h7.get('med', {}).get('avg', 0):+.3f} "
          f"high={h7.get('high', {}).get('avg', 0):+.3f} | "
          f"separates={chk['signal_separates_at_7d']} "
          f"high_vs_low={chk['signal_high_vs_low_at_7d']}", flush=True)


def _check():
    cal = build_calibration()
    assert cal["snapshots"] > 0, "no snapshots loaded"
    for h, buckets in cal["feature_backtest"].items():
        for b, m in buckets.items():
            assert m["n"] >= 0 and isinstance(m["avg"], float), f"bad bucket {h}/{b}"
    print("OK", {h: {b: cal['feature_backtest'][h][b]['n'] for b in ('low', 'med', 'high')}
                 for h in cal['feature_backtest']})


if __name__ == "__main__":
    _check() if "--check" in sys.argv else main()
