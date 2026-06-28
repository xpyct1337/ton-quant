#!/usr/bin/env python3
"""TON Quant v3.0 — AI Smart-Money Desk: single live-data check (spec §10).

Asserts on data/desk/verdicts.json (produced by scripts/desk.py on real data/):
  1. schema: date/model present; wallets have manip_risk + copy_ok; tokens have
     sym + manip_risk.
  2. every already wash-banned token (data/paper/bots.json -> wash_ban) that the
     desk surfaced gets manip_risk == "high".
  3. property: no wallet with manip_risk == "high" is copy_ok == true.

Run from repo root after a desk run:  python3 scripts/desk_test.py
"""
import json, sys
from desk_features import load

V = load("data/desk/verdicts.json", None)
assert V is not None, "data/desk/verdicts.json missing — run scripts/desk.py first"

# 1. schema
assert V.get("date") and V.get("model"), "verdicts missing date/model"
assert isinstance(V.get("wallets"), list) and V["wallets"], "no wallets"
assert isinstance(V.get("tokens"), list) and V["tokens"], "no tokens"
for w in V["wallets"]:
    assert w.get("manip_risk") in ("low", "med", "high"), f"bad wallet risk: {w}"
    assert isinstance(w.get("copy_ok"), bool), f"wallet copy_ok not bool: {w}"
for t in V["tokens"]:
    assert t.get("sym") and t.get("manip_risk") in ("low", "med", "high"), f"bad token: {t}"

# 2. wash-banned tokens -> high
idx = (load("data/index.json", {}) or {}).get("tokens", {})
snap_syms = {t.get("sym") for t in V["tokens"]}
wash_ban = (load("data/paper/bots.json", {}) or {}).get("wash_ban", {})
ban_syms = set()
for addr in wash_ban:
    ban_syms.add(idx.get(addr) or (addr[:10] + "…"))
by_sym = {t["sym"]: t for t in V["tokens"]}
checked = 0
for sym in ban_syms:
    t = by_sym.get(sym)
    if not t:
        continue
    assert t["manip_risk"] == "high", f"wash-banned {sym} not high: {t}"
    checked += 1
assert checked > 0, "no wash-banned tokens surfaced in verdicts to check"

# 3. property: high risk => not copy_ok
bad = [w for w in V["wallets"] if w["manip_risk"] == "high" and w["copy_ok"]]
assert not bad, f"high-risk wallets marked copy_ok: {[w['addr'][:12] for w in bad]}"

high_w = sum(1 for w in V["wallets"] if w["manip_risk"] == "high")
print(f"PASS  date={V['date']} model={V['model']}  "
      f"wallets={len(V['wallets'])} (high={high_w})  tokens={len(V['tokens'])}  "
      f"wash_ban_high_checked={checked}")
