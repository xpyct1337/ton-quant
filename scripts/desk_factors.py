#!/usr/bin/env python3
"""TON Quant v3.0 — factor DSL + active registry (Phase 2 researcher).

Factors are SAFE JSON expression trees over whitelisted snapshot fields — never
executed code. desk_researcher.py discovers them; desk.py applies the active set.
Active factors can only RAISE a token's risk (max with floor), never lower it.

Active set: data/desk/factors_active.json   (cap MAX_ACTIVE)
Audit log : data/desk/factors_history.json  (append-only, ring buffer of MAX_HISTORY)
CLI: python3 scripts/desk_factors.py --list | --disable <id> [--note "..."]
Run from repo root. Self-test: scripts/desk_factors_test.py
"""
import json, os, sys, time

ACTIVE = "data/desk/factors_active.json"
HISTORY = "data/desk/factors_history.json"
MAX_ACTIVE = 8
MAX_HISTORY = 1000   # ring buffer size for the append-only audit log
FIELDS = ("vol24", "tvl", "holders", "buys", "sells", "mcap", "supply", "price", "pools")
DERIVED = ("buy_sell_skew", "vol_tvl")
# Track B collectors (present once the cloud has run them; factors referencing a
# missing field simply don't fire): snapshot pool-structure + holders + trade flows.
AUX_FIELDS = ("spread", "top_pool", "age_d",          # snapshot.py pool structure
              "top10", "top25", "hhi",                # wallets.py holder concentration
              "ubuyers", "buyer_conc", "buy_share",   # flows.py trade flows
              "mentions")                             # social.py Telegram cashtags
OPS = ("div", "mul", "sub", "add", "abs", "min", "max", "const")


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def derived(fields):
    b, s = fields.get("buys") or 0, fields.get("sells") or 0
    v, t = fields.get("vol24") or 0, fields.get("tvl") or 0
    d = dict(fields)
    d["buy_sell_skew"] = abs(b - s) / (b + s) if (b + s) > 0 else 0.0
    d["vol_tvl"] = v / t if t > 0 else 0.0
    return d


def eval_expr(expr, fields):
    """Recursively evaluate a whitelisted expression. Raises ValueError on unknown
    field/op (invalid factor). Division by zero -> 0.0. NO eval/exec."""
    if isinstance(expr, (int, float)):
        return float(expr)
    if isinstance(expr, str):
        if expr not in fields and expr not in DERIVED:
            raise ValueError(f"unknown field {expr}")
        return float(fields.get(expr, 0) or 0)
    if not isinstance(expr, dict) or "op" not in expr:
        raise ValueError("bad expr")
    op = expr["op"]
    if op not in OPS:
        raise ValueError(f"unknown op {op}")
    if op == "const":
        return float(expr.get("value", 0))
    a = eval_expr(expr["a"], fields)
    if op == "abs":
        return abs(a)
    b = eval_expr(expr["b"], fields)
    if op == "div":
        return a / b if b != 0 else 0.0
    return {"mul": a * b, "sub": a - b, "add": a + b,
            "min": min(a, b), "max": max(a, b)}[op]


def factor_signal(spec, raw_fields):
    """Scalar signal for a token; None if the factor is invalid for these fields."""
    try:
        return eval_expr(spec["expr"], derived(raw_fields))
    except Exception:
        return None


def fires(spec, signal):
    if signal is None:
        return False
    thr = spec.get("threshold", 0)
    return signal > thr if spec.get("direction") == "high_is_bad" else signal < thr


def apply_active(raw_fields, active=None):
    """-> (risk_level, flags) contributed by active factors. Only raises risk:
    1 fired factor -> 'med', >=2 -> 'high'. Never lowers (caller maxes with floor)."""
    active = active if active is not None else load(ACTIVE, [])
    flags = [s["id"] for s in active if fires(s, factor_signal(s, raw_fields))]
    risk = "high" if len(flags) >= 2 else ("med" if flags else "low")
    return risk, flags


# ---------- registry ----------
def load_active():
    return load(ACTIVE, [])


def _save_active(active):
    os.makedirs("data/desk", exist_ok=True)
    with open(ACTIVE, "w") as f:
        json.dump(active, f, ensure_ascii=False, indent=2)


def history_append(action, factor, metrics=None, reason=""):
    h = load(HISTORY, [])
    h.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": action,
              "factor": factor, "metrics": metrics or {}, "reason": reason})
    h = h[-MAX_HISTORY:]          # conytail: ring buffer — bounds file size / git churn
    os.makedirs("data/desk", exist_ok=True)
    with open(HISTORY, "w") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)


def trials_count():
    """Count of DISTINCT proposed factor expressions, not raw attempts. The
    anti-overfit deflated bar should tighten with genuinely new ideas tried, not
    with how many times the LLM re-proposed the same handful of exprs (it will,
    at temperature>0, over a 24/7 idle-filler loop) — else the bar collapses
    toward an unreachable p-value and the gate closes forever."""
    seen = {json.dumps(e["factor"].get("expr"), sort_keys=True)
            for e in load(HISTORY, []) if e["action"] == "proposed"}
    return len(seen)


def promote(spec, metrics, reason="auto"):
    """Add to active if not a dup and there is room (or it beats the weakest)."""
    active = load_active()
    if any(a.get("expr") == spec["expr"] for a in active):
        return False
    def rank(a):
        return a.get("metrics", {}).get("oos", {}).get("wilson_lo") or 0
    if len(active) >= MAX_ACTIVE:
        weakest = min(active, key=rank)
        if rank({"metrics": metrics}) <= rank(weakest):
            return False
        active.remove(weakest)
        history_append("demoted", weakest, weakest.get("metrics"), "evicted by stronger")
    entry = {**spec, "metrics": metrics, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    active.append(entry)
    _save_active(active)
    history_append("promoted", entry, metrics, reason)
    return True


def demote(factor_id, reason="auto"):
    active = load_active()
    keep = [a for a in active if a.get("id") != factor_id]
    if len(keep) == len(active):
        return False
    _save_active(keep)
    history_append("demoted", {"id": factor_id}, reason=reason)
    return True


def main(argv):
    if "--list" in argv:
        for a in load_active():
            print(a["id"], a.get("direction"), a.get("threshold"),
                  "oos_lo=", a.get("metrics", {}).get("oos", {}).get("wilson_lo"))
    elif "--disable" in argv:
        fid = argv[argv.index("--disable") + 1]
        note = argv[argv.index("--note") + 1] if "--note" in argv else "manual"
        ok = demote(fid, reason=f"disabled: {note}")
        print("disabled" if ok else "not found", fid)
    else:
        print("usage: --list | --disable <id> [--note ...]")


if __name__ == "__main__":
    main(sys.argv[1:])
