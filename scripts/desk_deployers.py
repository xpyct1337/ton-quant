#!/usr/bin/env python3
"""Deployer registry: repeat-offender scoring from accumulated snapshot history.

snapshot.py records each token's `admin` (deployer) daily since 01.07.2026. This
module aggregates: deployer -> tokens launched -> how many "rugged" (wash-banned by
the detector, or price collapsed to <20% of its observed peak). A new token from a
wallet whose previous tokens rugged is high-risk BEFORE any market signal exists —
the literature's strongest cheap rug predictor.

Output data/desk/deployers.json:
  {"deployers": {admin: {tokens, rugged, rug_rate}}, "by_token": {addr: dep_rug}}

dep_rug feeds agent-1's LIVE evidence only — NOT the researcher's historical gate
(a full-history score applied to past dates would be lookahead bias).

Run from repo root (worker calibrate cadence). Self-test: desk_deployers_test.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_features import load, load_snaps  # noqa: E402

COLLAPSE = 0.2   # last price below 20% of observed peak = collapsed


def token_outcomes(snaps, wash_ban):
    """{token_addr: {"admin": last-known admin, "rugged": bool}} from history."""
    px, admin = {}, {}
    for d in sorted(snaps):
        for a, t in (snaps[d].get("tokens", {}) or {}).items():
            if t.get("price"):
                px.setdefault(a, []).append(t["price"])
            if t.get("admin"):
                admin[a] = t["admin"]
    out = {}
    for a, dep in admin.items():
        p = px.get(a, [])
        collapsed = len(p) >= 5 and p[-1] < COLLAPSE * max(p)
        out[a] = {"admin": dep, "rugged": (a in wash_ban) or collapsed}
    return out


def build_registry(outcomes):
    deps = {}
    for a, o in outcomes.items():
        e = deps.setdefault(o["admin"], {"tokens": 0, "rugged": 0})
        e["tokens"] += 1
        e["rugged"] += 1 if o["rugged"] else 0
    for e in deps.values():
        e["rug_rate"] = round(e["rugged"] / e["tokens"], 3)
    by_token = {a: deps[o["admin"]]["rug_rate"] for a, o in outcomes.items()}
    return {"deployers": deps, "by_token": by_token}


def main():
    snaps = load_snaps()
    wash_ban = set((load("data/paper/bots.json", {}) or {}).get("wash_ban", {}).keys())
    reg = build_registry(token_outcomes(snaps, wash_ban))
    os.makedirs("data/desk", exist_ok=True)
    with open("data/desk/deployers.json", "w") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
    n = len(reg["deployers"])
    hot = sum(1 for e in reg["deployers"].values() if e["rug_rate"] > 0)
    print(f"deployers: {n} known ({hot} with rugs), {len(reg['by_token'])} tokens scored", flush=True)


if __name__ == "__main__":
    main()
