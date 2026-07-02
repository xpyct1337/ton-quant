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
import json, os, sys, math, glob, statistics
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


# ---------- forward returns (shared by calibration / researcher / copytrade / desk) ----------
def load_snaps():
    """{date: snapshot_dict} for every data/snapshots/<date>.json."""
    out = {}
    for f in sorted(glob.glob("data/snapshots/*.json")):
        out[os.path.basename(f)[:-5]] = load(f, {})
    return out


def _price(snaps, date, addr):
    t = (snaps.get(date, {}).get("tokens", {}) or {}).get(addr)
    return t.get("price") if t else None


def forward_excess(snaps, date, addr, k):
    """Forward EXCESS return of addr from `date` to the k-th later available date.

    Excess = token raw return minus the mean raw return of all tokens priced on
    both dates. Returns None if there is no k-th later snapshot or no price."""
    dates = sorted(snaps)
    if date not in dates:
        return None
    i = dates.index(date)
    if i + k >= len(dates):
        return None
    d2 = dates[i + k]
    p0, p1 = _price(snaps, date, addr), _price(snaps, d2, addr)
    if not p0 or not p1:
        return None
    raw = p1 / p0 - 1.0
    rets = []
    for a in (snaps[date].get("tokens", {}) or {}):
        a0, a1 = _price(snaps, date, a), _price(snaps, d2, a)
        if a0 and a1:
            rets.append(a1 / a0 - 1.0)
    mean = sum(rets) / len(rets) if rets else 0.0
    return raw - mean


# ---------- backward-looking daily-series features (for the researcher DSL) ----------
# Daily resolution only — the pipeline commits daily snapshots, no intraday data.
SERIES_FIELDS = ("ret_1d", "mom_3d", "mom_7d", "vol_z", "rvol", "trend", "hgrow_7d")


def _series(snaps, date, addr, key):
    """Values of `key` for addr from oldest snapshot up to `date` inclusive (gaps dropped)."""
    out = []
    for d in sorted(snaps):
        if d > date:
            break
        t = (snaps.get(d, {}).get("tokens", {}) or {}).get(addr)
        v = t.get(key) if t else None
        if v:
            out.append(v)
    return out


def series_feats(snaps, date, addr):
    """Time-series features as-of `date` from committed snapshots. Returns only keys
    with enough history — a factor referencing a missing one just won't fire on that
    token/date (eval raises -> no signal), the honest behaviour on thin history.
    Indices are observations-back (snapshots are ~daily and mostly contiguous)."""
    px = _series(snaps, date, addr, "price")
    vol = _series(snaps, date, addr, "vol24")
    hol = _series(snaps, date, addr, "holders")
    f = {}
    if len(px) >= 2:
        f["ret_1d"] = px[-1] / px[-2] - 1.0            # short reversal (low last-ret tends to outperform)
    if len(px) >= 4:
        f["mom_3d"] = px[-1] / px[-4] - 1.0            # cross-sectional momentum
    if len(px) >= 8:
        f["mom_7d"] = px[-1] / px[-8] - 1.0
    if len(px) >= 5:
        w = px[-10:]
        m = sum(w) / len(w)
        if m:
            f["trend"] = px[-1] / m - 1.0              # price vs recent mean
        rets = [w[i] / w[i - 1] - 1.0 for i in range(1, len(w)) if w[i - 1]]
        if len(rets) >= 2:
            f["rvol"] = round(statistics.pstdev(rets), 4)   # realized volatility (risk/sizing)
    if len(vol) >= 5:
        w = vol[-10:]
        sd = statistics.pstdev(w)
        if sd > 0:
            f["vol_z"] = round((vol[-1] - sum(w) / len(w)) / sd, 3)   # volume anomaly (pump trigger)
    if len(hol) >= 8 and hol[-8]:
        f["hgrow_7d"] = hol[-1] / hol[-8] - 1.0        # holder growth (organic interest proxy)
    return {k: round(v, 4) if isinstance(v, float) else v for k, v in f.items()}


# ---------- Track B aux data (holders concentration + trade flows) ----------
def load_aux():
    """{date: {token_addr: fields}} merged from data/holders/ and data/flows/
    (cloud Track-B collectors). Empty until they've run — features simply absent,
    factors referencing them won't fire (honest degradation)."""
    out = {}
    for d in ("data/holders", "data/flows", "data/social", "data/forensics"):
        for f in glob.glob(d + "/*.json"):
            doc = load(f, {})
            day = os.path.basename(f)[:-5]
            for a, m in (doc.get("tokens") or {}).items():
                out.setdefault(day, {}).setdefault(a, {}).update(m)
    return out


def mention_velocity():
    """{addr: m_vel} = latest social day's mentions minus the previous day's.
    0-defaulted: a token absent from an EXISTING social file had 0 mentions that
    day (unlike holders/flows, absence there means 'not measured')."""
    files = sorted(glob.glob("data/social/*.json"))
    if len(files) < 2:
        return {}
    prev, cur = load(files[-2], {}), load(files[-1], {})
    pt, ct = prev.get("tokens", {}) or {}, cur.get("tokens", {}) or {}
    return {a: ct.get(a, {}).get("mentions", 0) - pt.get(a, {}).get("mentions", 0)
            for a in set(ct) | set(pt)}


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
    # universe covers the wider discovery set — resolves names for non-tracked tokens
    for t in (load("data/universe.json", {}) or {}).get("tokens", []):
        if t.get("addr") and t.get("sym"):
            idx.setdefault(t["addr"], t["sym"])
    snap_files = sorted(glob.glob("data/snapshots/*.json"))
    snap = (load(snap_files[-1], {}) or {}).get("tokens", {}) if snap_files else {}
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
    snaps = load_snaps()                              # for recent_fwd (real measured outcome)

    def recent_fwd(waddr, horizon=3):
        """Avg forward EXCESS return of this wallet's first-entries (realized only).

        Unlike the roster 'edge' field (a stale, full-window average — can disagree
        with what actually just happened), this is the same forward math the
        copytrade book uses: a recency-true read of whether following this wallet
        would have paid off lately. None if no entry has a realized outcome yet."""
        exs = [forward_excess(snaps, d, a, horizon) for a, d in first.get(waddr, {}).items()]
        exs = [e for e in exs if e is not None]
        return round(sum(exs) / len(exs), 4) if exs else None

    latest = sorted(snaps)[-1] if snaps else date
    aux_latest = load_aux().get(latest, {})           # Track B: holders conc + trade flows
    dep_rug = (load("data/desk/deployers.json", {}) or {}).get("by_token", {})
    m_vel = mention_velocity()                        # live-only evidence for agent-1

    def tok_feats(addr):
        t = snap.get(addr, {})
        fields = {k: t.get(k) for k in
                  ("vol24", "tvl", "holders", "buys", "sells",
                   "mcap", "supply", "price", "pools", "spread", "top_pool", "age_d")
                  if t.get(k) is not None} if t else {}
        if t:
            fields.update(series_feats(snaps, latest, addr))   # +time-series for factors
            fields.update(aux_latest.get(addr, {}))            # +holder conc / flow metrics
            if addr in dep_rug:
                fields["dep_rug"] = dep_rug[addr]              # deployer track record
            if addr in m_vel:
                fields["m_vel"] = m_vel[addr]                  # mention velocity (social)
        return {
            "wash": token_wash(addr, wash_ban),
            "vol_auth": vol_auth(t) if t else 0.5,   # unknown -> neutral
            "conc": conc(t) if t else 0.5,
            "fields": fields,
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
            "recent_fwd": recent_fwd(w["addr"]),
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
