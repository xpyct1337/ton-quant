#!/usr/bin/env python3
"""TON Quant v3.0 — AI Smart-Money Desk: deterministic feature layer (spec §5/§6).

Builds compact, normalized (0..1) feature-JSON per roster wallet and per token
from data the v2 pipeline ALREADY collects — no new fetches (conytail / MVP).
The LLM agents (scripts/desk.py) read these features, never the raw data.

Features:
  wash            reuse existing Wash detector: 1.0 if the token is in
                  data/paper/bots.json -> wash_ban, else 0.0. The detector only
                  emits a ban list, so wash is binary at MVP.
  co_entry        coordination: fraction of a wallet's tokens it FIRST entered in
                  the same dated slice as >=K other roster wallets
                  (data/wallets/<date>.json diffs) — proxy for bundling/lure.
  vol_auth        volume authenticity 0..1 (HIGH = authentic). Lowered by extreme
                  vol24/tvl and by buys/sells imbalance.
  conc            holder concentration 0..1 (HIGH = concentrated). MVP PROXY from
                  holder COUNT (few holders = concentrated); real top10/HHI needs
                  a holder-distribution fetch -> Phase 2 (not in snapshot data).
  edge_dispersion 0..1 (HIGH = thin/lucky): edge from few names (small ne) = luck,
                  from many = skill. Proxy 1/(1+ne).

Run from repo root. stdlib only. Self-check:  python3 scripts/desk_features.py --check
"""
import json, os, sys, math, glob
from collections import defaultdict

CO_ENTRY_K = 2   # >=K roster wallets entering a token in one slice = coordinated


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _latest(globpat):
    files = sorted(glob.glob(globpat))
    return files[-1] if files else None


# ---------- per-token features ----------
def token_wash(addr, wash_ban):
    return 1.0 if addr in wash_ban else 0.0


def vol_auth(t):
    """Authenticity 0..1 (high = authentic). t = snapshot token dict."""
    tvl = t.get("tvl") or 0
    vol = t.get("vol24") or 0
    b = t.get("buys") or 0
    s = t.get("sells") or 0
    vt = vol / tvl if tvl > 0 else 0.0
    ex_vol = clamp(vt / 3.0)                  # vol/TVL >= 3x/day -> fully extreme
    skew = abs(b - s) / (b + s) if (b + s) > 0 else 0.0
    inauth = clamp(0.6 * ex_vol + 0.4 * skew)
    return round(1.0 - inauth, 3)


def conc(t):
    """Holder concentration 0..1 (high = concentrated). Proxy from holder count."""
    h = t.get("holders") or 0
    if h <= 0:
        return 1.0
    norm = clamp((math.log10(h) - 2) / (6 - 2))   # 100 holders->0 .. 1e6->1
    return round(1.0 - norm, 3)


def edge_dispersion(ne):
    ne = ne or 0
    return round(1.0 / (1.0 + max(ne, 0)), 3)


# ---------- co-entry from dated wallet diffs ----------
def first_entries():
    """{wallet_addr: {token_addr: first_seen_date}} across data/wallets/<date>.json."""
    first = {}
    for f in sorted(glob.glob("data/wallets/*.json")):       # ascending -> earliest wins
        date = os.path.basename(f)[:-5]
        d = load(f, {})
        for waddr, info in (d.get("held") or {}).items():
            for taddr in (info.get("toks") or {}):
                first.setdefault(waddr, {}).setdefault(taddr, date)
    return first


def co_entry_scores(roster_addrs, k=CO_ENTRY_K):
    first = first_entries()
    bydate = defaultdict(set)                 # (token_addr, date) -> {roster wallet}
    for waddr, toks in first.items():
        if waddr not in roster_addrs:
            continue
        for taddr, date in toks.items():
            bydate[(taddr, date)].add(waddr)
    scores = {}
    for waddr in roster_addrs:
        toks = first.get(waddr, {})
        if not toks:
            scores[waddr] = 0.0
            continue
        coent = sum(1 for taddr, date in toks.items() if len(bydate[(taddr, date)]) >= k)
        scores[waddr] = round(coent / len(toks), 3)
    return scores, first


# ---------- assembly ----------
def build_features():
    meta = load("data/wallets.json", {})
    roster = meta.get("roster", [])
    date = meta.get("date", "")

    idx = (load("data/index.json", {}) or {}).get("tokens", {})   # addr -> sym
    snap_file = _latest("data/snapshots/*.json")
    snap = (load(snap_file, {}) or {}).get("tokens", {}) if snap_file else {}
    wash_ban = set((load("data/paper/bots.json", {}) or {}).get("wash_ban", {}).keys())

    # sym -> addrs (invert index, augment with snapshot)
    sym2addr = defaultdict(set)
    for a, sym in idx.items():
        sym2addr[sym].add(a)
    for a, t in snap.items():
        if t.get("sym"):
            sym2addr[t["sym"]].add(a)

    roster_addrs = {w["addr"] for w in roster}
    ce_scores, first = co_entry_scores(roster_addrs)

    def tok_feats(addr):
        t = snap.get(addr, {})
        return {
            "wash": token_wash(addr, wash_ban),
            "vol_auth": vol_auth(t) if t else 0.5,   # unknown -> neutral
            "conc": conc(t) if t else 0.5,
            "fields": {k: t.get(k) for k in                 # raw snapshot fields for factors
                       ("vol24", "tvl", "holders", "buys", "sells",
                        "mcap", "supply", "price", "pools")} if t else {},
        }

    # ---- wallet features ----
    wallets = []
    for w in roster:
        # the wallet's held token ADDRS: prefer dated `held`, fall back to sym map
        addrs = list(first.get(w["addr"], {}).keys())
        if not addrs:
            for sym in w.get("toks", []):
                addrs += list(sym2addr.get(sym, []))
        # wash is known for every addr (ban list); liquidity features only over
        # addrs we actually have snapshot data for (no neutral-default dilution).
        present = [a for a in addrs if a in snap]
        wallets.append({
            "addr": w["addr"], "name": w.get("name"),
            "conv": w.get("conv"), "edge": w.get("edge"),
            "win": w.get("win"), "ne": w.get("ne"), "toks": w.get("toks", []),
            "wash": round(max([token_wash(a, wash_ban) for a in addrs] or [0.0]), 3),
            "co_entry": ce_scores.get(w["addr"], 0.0),
            "vol_auth": round(min([vol_auth(snap[a]) for a in present] or [1.0]), 3),
            "conc": round(max([conc(snap[a]) for a in present] or [0.0]), 3),
            "edge_dispersion": edge_dispersion(w.get("ne")),
        })

    # ---- token features (roster tokens ∪ wash-banned) ----
    tok_addrs = set(wash_ban)
    for w in roster:
        for sym in w.get("toks", []):
            tok_addrs |= sym2addr.get(sym, set())
        tok_addrs |= set(first.get(w["addr"], {}).keys())

    tokens = []
    for a in sorted(tok_addrs):
        sym = idx.get(a) or (snap.get(a, {}) or {}).get("sym") or (a[:10] + "…")
        f = tok_feats(a)
        tokens.append({"sym": sym, "addr": a, **f})

    return {"date": date, "wallets": wallets, "tokens": tokens}


def _check():
    feats = build_features()
    w, t = feats["wallets"], feats["tokens"]
    assert w, "no wallets"
    assert t, "no tokens"
    keys01 = ("wash", "co_entry", "vol_auth", "conc", "edge_dispersion")
    for x in w:
        for k in keys01:
            v = x[k]
            assert 0.0 <= v <= 1.0, f"wallet {x['addr']} {k}={v} out of 0..1"
    for x in t:
        for k in ("wash", "vol_auth", "conc"):
            assert 0.0 <= x[k] <= 1.0, f"token {x['sym']} {k} out of 0..1"
    wash_ban = set((load("data/paper/bots.json", {}) or {}).get("wash_ban", {}).keys())
    banned = [x for x in t if x["addr"] in wash_ban]
    assert banned, "no wash_ban tokens surfaced"
    assert all(x["wash"] == 1.0 for x in banned), "wash_ban token without wash=1.0"
    co = sum(1 for x in w if x["co_entry"] > 0)
    print(f"OK  date={feats['date']}  wallets={len(w)}  tokens={len(t)}  "
          f"wash_ban_surfaced={len(banned)}  co_entry>0={co}")
    # show a couple of samples
    for x in w[:2]:
        print("  wallet", x["name"] or x["addr"][:12], {k: x[k] for k in keys01})


if __name__ == "__main__":
    if "--check" in sys.argv:
        _check()
    else:
        print(json.dumps(build_features(), ensure_ascii=False, indent=2))
