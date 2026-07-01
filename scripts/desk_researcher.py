#!/usr/bin/env python3
"""TON Quant v3.0 — agent-researcher (Phase 2): propose -> gate -> promote.

The LLM proposes ONE constrained-DSL factor; a deterministic walk-forward OOS gate
(reusing score.py Wilson/sign-test on forward EXCESS returns) decides if it predicts
underperformance robustly, with an anti-overfit deflated bar (stricter as the LLM
tries more factors). Survivors auto-promote into data/desk/factors_active.json with a
full append-only history. revalidate() demotes active factors that decay.

Run from repo root:
  python3 scripts/desk_researcher.py            # one propose->gate->promote pass
  python3 scripts/desk_researcher.py --revalidate
Self-test (gate only, no LLM): scripts/desk_researcher_test.py
"""
import json, os, sys, hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import wilson_lo, sign_test_p                       # noqa: E402
from desk_calibration import load_snaps, forward_excess        # noqa: E402
from desk_features import series_feats, SERIES_FIELDS, load_aux  # noqa: E402
from desk_factors import (factor_signal, fires, FIELDS, DERIVED, AUX_FIELDS, OPS,  # noqa: E402
                          load, HISTORY, load_active, promote, demote,
                          history_append, trials_count)
from desk import llm                                           # noqa: E402

BASE_P = 0.05
MIN_FIRED = 5          # need this many fired tokens in each split
MODEL = os.environ.get("DESK_MODEL", "qwen3-4b-4bit")


def _stats(ex):
    n = len(ex)
    losers = sum(1 for e in ex if e < 0)
    return {"n": n, "losers": losers, "wilson_lo": wilson_lo(losers, n),
            "sign_p": sign_test_p(losers, n - losers),
            "avg": round(sum(ex) / n, 4) if n else 0.0}


def _collect(spec, snaps, dates, aux):
    ex = []
    for d in dates:
        for addr, t in (snaps[d].get("tokens", {}) or {}).items():
            # as-of-date time-series + Track-B aux (holders/flows) for the factor
            feat = {**t, **series_feats(snaps, d, addr), **aux.get(d, {}).get(addr, {})}
            if fires(spec, factor_signal(spec, feat)):
                e = forward_excess(snaps, d, addr, spec.get("horizon", 7))
                if e is not None:
                    ex.append(e)
    return ex


def gate(spec, snaps, trials):
    """Walk-forward OOS gate. Returns dict(in_sample, oos, bar, passed) or None."""
    dates = sorted(snaps)
    if len(dates) < 6:
        return None
    aux = load_aux()
    cut = int(len(dates) * 0.6)
    si = _stats(_collect(spec, snaps, dates[:cut], aux))
    so = _stats(_collect(spec, snaps, dates[cut:], aux))
    bar = BASE_P / (trials ** 0.5 if trials > 0 else 1)
    def sig(s):                                  # majority underperform, significant, neg avg
        return (s["n"] >= MIN_FIRED and s["wilson_lo"] is not None and s["wilson_lo"] > 50.0
                and s["sign_p"] is not None and s["sign_p"] < bar and s["avg"] < 0)
    return {"in_sample": si, "oos": so, "bar": round(bar, 4),
            "passed": bool(sig(si) and sig(so))}


# ---------- LLM proposal ----------
def _depth(expr):
    if not isinstance(expr, dict):
        return 0
    return 1 + max((_depth(expr[k]) for k in ("a", "b") if k in expr), default=0)


def _recent_exprs(limit=12):
    """exprs already tried (active + recent history) so the LLM explores new ones."""
    seen = [json.dumps(a["expr"]) for a in load_active()]
    for e in load(HISTORY, [])[-limit:]:
        ex = e.get("factor", {}).get("expr")
        if ex:
            seen.append(json.dumps(ex))
    return list(dict.fromkeys(seen))


# (label, field menu) rotated deterministically each pass — a weak model can't be
# steered by a soft hint, so we hand it ONLY this round's fields to force coverage.
FOCUSES = (
    ("liquidity vs size", ["tvl", "mcap", "vol24"]),
    ("buy/sell flow imbalance", ["buys", "sells", "buy_sell_skew"]),
    ("price momentum & trend", ["mom_3d", "mom_7d", "trend"]),
    ("volume anomaly", ["vol_z", "vol_tvl", "rvol"]),
    ("short-term reversal", ["ret_1d", "price"]),
    ("holder dynamics", ["holders", "hgrow_7d"]),
    # Track B (fields appear as the cloud collectors accumulate history):
    ("holder concentration", ["top10", "top25", "hhi"]),
    ("organic vs bot buyer flow", ["ubuyers", "buyer_conc", "buy_share"]),
    ("pool structure & age", ["spread", "top_pool", "age_d"]),
    ("social attention", ["mentions", "hgrow_7d", "ubuyers"]),
)


def _research_sys(active_exprs, label, menu):
    avoid = "; ".join(active_exprs) or "none"
    return (
        "You are a quant factor researcher hunting a factor that predicts a token's FUTURE "
        "underperformance (manipulation/dump risk). THIS ROUND theme: " + label + ". "
        "Build the expr using ONLY these fields: " + ", ".join(menu) + " (and numeric "
        "constants). Allowed ops: " + ", ".join(OPS) + ". "
        "Keep expr SHALLOW: ONE op over two of those fields (or a field and a number), max "
        "depth 2. Do NOT use fields outside the list. Do NOT deeply nest. "
        'Reply ONLY JSON: {"id":"f_x","expr":{"op":..,"a":..,"b":..},'
        '"direction":"high_is_bad"|"low_is_bad","threshold":<number>,"horizon":7}. '
        "Avoid these existing exprs: " + avoid)


def propose():
    label, menu = FOCUSES[trials_count() % len(FOCUSES)]   # rotate family each pass
    try:                                              # temp>0 -> explores varied factors
        out = llm(MODEL, _research_sys(_recent_exprs(), label, menu),
                  "Propose one new factor.", temperature=0.8)
    except Exception as e:                            # noqa: BLE001
        return None, f"llm_unavailable: {type(e).__name__}"
    if not isinstance(out, dict) or "expr" not in out:
        return None, "no expr"
    if _depth(out["expr"]) > 3:                        # reject runaway nesting
        return None, "expr too deep"
    # validate it evaluates on a sample (rejects unknown fields/ops safely)
    if factor_signal(out, {k: 1.0 for k in FIELDS + SERIES_FIELDS + AUX_FIELDS}) is None:
        return None, "invalid expr"
    out["direction"] = out.get("direction") if out.get("direction") in (
        "high_is_bad", "low_is_bad") else "high_is_bad"
    out.setdefault("threshold", 1.0)
    out.setdefault("horizon", 7)
    out["id"] = "f_" + hashlib.md5(                   # stable across processes
        json.dumps(out["expr"], sort_keys=True).encode()).hexdigest()[:8]
    return out, "ok"


def research_once():
    snaps = load_snaps()
    spec, why = propose()
    if not spec:
        return f"propose failed: {why}"
    history_append("proposed", spec, reason=why)
    g = gate(spec, snaps, trials_count())
    if not g:
        history_append("rejected", spec, reason="insufficient data")
        return f"rejected {spec['id']}: insufficient data"
    if g["passed"]:
        spec["metrics"] = g
        ok = promote(spec, g)
        return f"{'promoted' if ok else 'rejected(dup/weak)'} {spec['id']} oos_lo={g['oos']['wilson_lo']}"
    history_append("rejected", spec, g, "failed gate")
    return f"rejected {spec['id']}: failed gate (oos_lo={g['oos']['wilson_lo']})"


def revalidate():
    snaps = load_snaps()
    n = 0
    for a in load_active():
        g = gate(a, snaps, trials_count())
        if not g or not g["passed"]:
            demote(a["id"], reason="revalidate: decayed")
            n += 1
    return f"revalidate: demoted {n}"


def main(argv):
    print(revalidate() if "--revalidate" in argv else research_once(), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
