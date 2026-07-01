#!/usr/bin/env python3
"""Transfer forensics: bundle detection via funding-source clustering (MELT method).

For each tracked token's top-25 holders, find who FUNDED each holder wallet (source
of its oldest transaction — immutable, so cached forever in data/funding.json; the
first run pays ~900 lookups, daily increments are a few dozen). Holders of the same
token sharing one funder form a bundle cluster — coordinated supply masquerading as
distributed holders (MELT: on average 36.5% of memecoin supply is held this way).

CEX caveat: exchange withdrawal wallets legitimately fund thousands of wallets, so
funders seen funding > MEGA_FUNDER wallets across the whole registry are excluded
from clustering. Residual false positives are possible; bundle is EVIDENCE for the
desk's agents, not an automatic ban.

Output data/forensics/<date>.json per token:
  bundle      share of top-25 holder balance sitting in funding clusters (0..1)
  clusters    number of clusters (>=2 wallets sharing a non-mega funder)
  max_cluster wallet count of the biggest cluster

Launch-block snipe detection = Phase 2 (needs launch-event pagination, young tokens).
Non-fatal workflow step. stdlib only. Self-test: FORENSICS_SELFTEST=1
"""
import json, os, time, datetime, urllib.request

KEY = "AEUCH5S5SBNE64AAAAAMCL5S6MOL6AFR42PEXAR3OL2K2VJTQS77IQCN7I3O54EQK76ZIFA"
TOPN = 25
MEGA_FUNDER = 20   # funder of >N wallets in the registry = CEX/service, not a bundle
PACE = 0.25
FUNDING = "data/funding.json"


def get(url):
    h = {"Accept": "application/json", "User-Agent": "tonquant-forensics",
         "Authorization": "Bearer " + KEY}
    for i in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30))
        except Exception:
            if i == 2:
                raise
            time.sleep(3 * (i + 1))


def funder_of(wallet):
    """Source address of the wallet's oldest transaction (its gas funder)."""
    d = get(f"https://tonapi.io/v2/blockchain/accounts/{wallet}/transactions?limit=1&sort_order=asc")
    txs = d.get("transactions") or []
    if not txs:
        return None
    return ((txs[0].get("in_msg") or {}).get("source") or {}).get("address")


def bundle_metrics(holders, funding, mega):
    """holders: [(owner_addr, balance)] top-N of one token; funding: {wallet: funder};
    mega: set of mega-funders to ignore. -> {bundle, clusters, max_cluster}."""
    groups = {}
    for w, bal in holders:
        f = funding.get(w)
        if f and f not in mega:
            groups.setdefault(f, []).append((w, bal))
    clusters = [g for g in groups.values() if len(g) >= 2]
    tot = sum(b for _, b in holders) or 1
    clustered = sum(b for g in clusters for _, b in g)
    return {"bundle": round(clustered / tot, 4), "clusters": len(clusters),
            "max_cluster": max((len(g) for g in clusters), default=0)}


def main():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    uni = json.load(open("data/universe.json"))
    toks = [t["addr"] for t in uni["tokens"] if t.get("tracked")]
    if os.environ.get("FORENSICS_LIMIT"):
        toks = toks[:int(os.environ["FORENSICS_LIMIT"])]
    try:
        funding = json.load(open(FUNDING))
    except Exception:
        funding = {}

    per_token, new = {}, 0
    for a in toks:
        try:
            d = get(f"https://tonapi.io/v2/jettons/{a}/holders?limit={TOPN}")
        except Exception:
            continue
        hs = []
        for hh in d.get("addresses", []):
            o = hh.get("owner") or {}
            w = o.get("address")
            if not w or o.get("name"):          # named wallets = CEX/pools/infra, skip
                continue
            hs.append((w, int(hh.get("balance") or 0)))
        per_token[a] = hs
        for w, _ in hs:
            if w not in funding:
                try:
                    funding[w] = funder_of(w)
                    new += 1
                except Exception:
                    pass
                time.sleep(PACE)
        time.sleep(PACE)

    json.dump(funding, open(FUNDING, "w"), separators=(",", ":"))
    # mega-funders across the whole registry = exchanges/services, not bundlers
    counts = {}
    for f in funding.values():
        if f:
            counts[f] = counts.get(f, 0) + 1
    mega = {f for f, n in counts.items() if n > MEGA_FUNDER}

    out = {a: bundle_metrics(hs, funding, mega) for a, hs in per_token.items() if hs}
    os.makedirs("data/forensics", exist_ok=True)
    doc = {"date": today, "tokens": out}
    json.dump(doc, open(f"data/forensics/{today}.json", "w"), separators=(",", ":"))
    json.dump(doc, open("data/forensics.json", "w"), separators=(",", ":"))
    flagged = sum(1 for m in out.values() if m["bundle"] > 0.2)
    print(f"forensics {today}: {len(out)} tokens, {new} new funding lookups, "
          f"{len(mega)} mega-funders excluded, {flagged} tokens with bundle>20%")


if __name__ == "__main__":
    if os.environ.get("FORENSICS_SELFTEST"):
        # W1,W2 funded by X (bundle, 60% of balance); W3 by CEX (mega); W4 unknown
        funding = {"W1": "X", "W2": "X", "W3": "CEX", "W4": None}
        holders = [("W1", 40), ("W2", 20), ("W3", 30), ("W4", 10)]
        m = bundle_metrics(holders, funding, mega={"CEX"})
        assert m == {"bundle": 0.6, "clusters": 1, "max_cluster": 2}, m
        print("selftest OK", m)
    else:
        main()
