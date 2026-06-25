#!/usr/bin/env python3
"""Copy-trading V1: smart-money roster from cross-token top-holder overlap.
For each tracked jetton, pull its top holders, drop non-copyable infra
(CEX hot wallets / DEX pools / scam / burn), and rank owner wallets by how many
tracked tokens they're a top holder of (breadth = ecosystem conviction).
Persists data/wallets.json (roster) + dated data/wallets/<date>.json so the
next run diffs positions and surfaces NEW entries = actual copy signals.
conytail: TONAPI only, stdlib, no per-wallet calls."""
import json, os, glob, time, datetime, urllib.request

KEY = "AEUCH5S5SBNE64AAAAAMCL5S6MOL6AFR42PEXAR3OL2K2VJTQS77IQCN7I3O54EQK76ZIFA"
TOPN, ROSTER = 25, 60
# substrings (lowercased) in owner.name that mark non-copyable infra/custody
INFRA = ("dex", "pool", "router", "vault", "bridge", "ston.fi", "dedust", "megaton",
         "tonco", "swap.coffee", "okx", "mexc", "bybit", "gate", "binance", "bitget",
         "htx", "kucoin", "bingx", "coinex", "bitfinex", "whitebit", "lbank", "xt.com",
         "kraken", "staking", "liquid", "treasury", " team", "reserve", "foundation",
         "escrow", "vesting", "lock", "burn", "deployer", "hot wallet", "bot",
         "rocket", "zero address", "null address")

def get(url):
    h = {"Accept": "application/json", "User-Agent": "tonquant-wallets", "Authorization": "Bearer " + KEY}
    for i in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30))
        except Exception:
            if i == 3:
                raise
            time.sleep(2 * (i + 1))

def is_infra(o):
    if o.get("is_scam"):
        return True
    n = (o.get("name") or "").lower()
    return any(k in n for k in INFRA)

def smart_score(edge, win, ne, n):
    # one number to rank "who to copy": shrunk edge x consistency x breadth bonus.
    # edge * ne/(ne+3) discounts thin samples (a +35% on 1 token shrinks hard);
    # * win/100 rewards systematic (not one-pump-lucky) pickers; (1+0.1*(n-2)) tilts
    # toward broader ecosystem conviction. Negative edge -> negative score (ranks last).
    if edge is None or win is None or ne == 0:
        return None
    return round(edge * (ne / (ne + 3)) * (win / 100) * (1 + 0.1 * (n - 2)), 2)

def main():
    D = "data"
    uni = json.load(open(D + "/universe.json"))
    toks = {t["addr"]: t["sym"] for t in uni["tokens"] if t.get("tracked")}
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    held = {}  # owner_addr -> {"name":.., "toks":{addr:rank}}
    ok = 0
    for a in toks:
        try:
            d = get(f"https://tonapi.io/v2/jettons/{a}/holders?limit={TOPN}")
        except Exception:
            continue
        ok += 1
        for rank, hh in enumerate(d.get("addresses", []), 1):
            o = hh.get("owner") or {}
            w = o.get("address")
            if not w or is_infra(o):
                continue
            e = held.setdefault(w, {"name": o.get("name"), "toks": {}})
            e["toks"][a] = rank
        time.sleep(0.3)

    # diff vs previous dated snapshot -> "new" tokens each roster wallet entered since
    snaps = sorted(glob.glob(D + "/wallets/*.json"))
    prev_h = (json.load(open(snaps[-1])).get("held", {})) if snaps else {}

    # token returns from price snapshots -> per-wallet "edge" = avg return of held
    # tokens (proxy for picking skill, not entry-PnL; ranks copy targets by results)
    psnaps = sorted(glob.glob(D + "/snapshots/*.json"))
    rets, edge_days = {}, 0
    if len(psnaps) >= 2:
        base = json.load(open(psnaps[-8 if len(psnaps) >= 8 else 0]))
        last = json.load(open(psnaps[-1]))
        edge_days = (datetime.date.fromisoformat(last["date"]) - datetime.date.fromisoformat(base["date"])).days
        bt, lt = base["tokens"], last["tokens"]
        for a in toks:
            pb, pl = (bt.get(a) or {}).get("price"), (lt.get(a) or {}).get("price")
            if pb and pl:
                rets[a] = (pl / pb - 1) * 100

    # roster: breadth desc, then best (lowest) rank
    roster = sorted(held.items(), key=lambda kv: (-len(kv[1]["toks"]), min(kv[1]["toks"].values())))
    out_roster = []
    for w, e in roster[:ROSTER]:
        if len(e["toks"]) < 2:  # need cross-token conviction to qualify as smart money
            continue
        pt = set((prev_h.get(w) or {}).get("toks", {}))
        new = [toks[a] for a in e["toks"] if pt and a not in pt]
        eh = [rets[a] for a in e["toks"] if a in rets]
        edge = round(sum(eh) / len(eh), 1) if eh else None
        # hit-rate: % of priced held tokens that are up over the window (consistency,
        # vs edge which one moonshot can dominate). ne = how many tokens it's based on.
        win = round(100 * sum(x > 0 for x in eh) / len(eh)) if eh else None
        ne = len(eh)
        out_roster.append({
            "addr": w, "name": e["name"], "n": len(e["toks"]),
            "toks": [toks[a] for a in sorted(e["toks"], key=lambda a: e["toks"][a])],
            "new": new,
            "edge": edge, "win": win, "ne": ne,
            # combined "who to copy" rank: shrunk edge x hit-rate x breadth (see fn)
            "smart": smart_score(edge, win, ne, len(e["toks"])),
        })
    # token-level consensus: how many ROSTER (smart) wallets hold each token =
    # crowding. Tokens many proven multi-token wallets converge on are the cleanest
    # copy targets — aggregates the wallet view into "what's smart money buying".
    fav = {}
    for r in out_roster:
        for t in r["toks"]:
            f = fav.setdefault(t, {"sym": t, "holders": 0, "edges": [], "new": 0})
            f["holders"] += 1
            if r["edge"] is not None:
                f["edges"].append(r["edge"])
            if t in r["new"]:
                f["new"] += 1
    favorites = sorted(
        ({"sym": f["sym"], "holders": f["holders"], "new": f["new"],
          "avg_edge": round(sum(f["edges"]) / len(f["edges"]), 1) if f["edges"] else None}
         for f in fav.values()),
        key=lambda x: (-x["holders"], -(x["avg_edge"] if x["avg_edge"] is not None else -1e9)))

    out = {"date": today, "scanned": ok, "wallets": len(held), "edge_days": edge_days,
           "roster_size": len(out_roster), "roster": out_roster, "favorites": favorites}
    os.makedirs(D + "/wallets", exist_ok=True)
    json.dump(out, open(D + "/wallets.json", "w"), separators=(",", ":"))
    json.dump({"date": today, "held": {w: {"name": e["name"], "toks": e["toks"]} for w, e in held.items()}},
              open(f"{D}/wallets/{today}.json", "w"), separators=(",", ":"))
    print(f"wallets {today}: scanned {ok}/{len(toks)} toks, {len(held)} wallets, "
          f"roster {len(out_roster)}, favorites {len(favorites)}, "
          f"new-entry signals {sum(len(r['new']) for r in out_roster)}")

if __name__ == "__main__":
    main()
