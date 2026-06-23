#!/usr/bin/env python3
"""Auto-discover the TON jetton universe from GeckoTerminal pools.
Writes data/universe.json (broad, for Screener) + data/cats.json (tracked subset).
conytail: one source (GeckoTerminal), stdlib only, overrides via tiny json files."""
import urllib.request, json, time, pathlib, datetime

D = pathlib.Path(__file__).resolve().parent.parent / "data"
PAGES, MINVOL, MINLIQ, UNIVERSE, TRACKED = 10, 5000, 3000, 200, 100
STABLE = ("USD", "DAI", "USDE", "USDQ")
STAKE = ("TSTON", "STTON", "HTON", "STAKED")

def _load(name, default):
    p = D / name
    return json.load(open(p)) if p.exists() else default

def _gecko(page):
    u = f"https://api.geckoterminal.com/api/v2/networks/ton/pools?page={page}&sort=h24_volume_usd_desc"
    r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=25))["data"]

def categorize(sym, addr, overrides):
    if addr in overrides:
        return overrides[addr]
    s = sym.upper()
    if any(k in s for k in STAKE):
        return "staking"
    if any(k in s for k in STABLE):
        return "stable"
    return "meme"  # conytail: defi isn't auto-detectable from gecko — use cat_overrides.json

def build():
    overrides = _load("cat_overrides.json", {})
    allow, block = set(_load("allowlist.json", [])), set(_load("blocklist.json", []))
    toks = {}
    for pg in range(1, PAGES + 1):
        try:
            data = _gecko(pg)
        except Exception:
            break
        for p in data:
            a, rel = p["attributes"], p["relationships"]
            bid = rel.get("base_token", {}).get("data", {}).get("id", "")
            if not bid.startswith("ton_"):
                continue
            addr = bid[4:]
            liq = float(a.get("reserve_in_usd") or 0)
            vol = float((a.get("volume_usd") or {}).get("h24") or 0)
            price = float(a.get("base_token_price_usd") or 0)
            mcap = float(a.get("fdv_usd") or a.get("market_cap_usd") or 0)
            d1 = float((a.get("price_change_percentage") or {}).get("h24") or 0)
            sym = (a.get("name") or "?/").split("/")[0].strip()
            if sym.upper() in ("TON", "WTON", "PTON"):
                continue  # conytail: native/wrapped TON is the quote, not a jetton
            t = toks.get(addr)
            if not t:
                toks[addr] = {"addr": addr, "sym": sym, "price": price, "mcap": mcap, "liq": liq, "vol24": vol, "d1": d1}
            else:
                t["vol24"] += vol
                if liq > t["liq"]:  # deepest pool wins for price/mcap/liq
                    t.update(price=price, mcap=mcap, liq=liq, d1=d1)
        time.sleep(2)  # conytail: gecko free tier ~30 req/min — 2s gap is safe

    rows = [t for a, t in toks.items()
            if a not in block and ((t["vol24"] >= MINVOL and t["liq"] >= MINLIQ) or a in allow)]
    rows.sort(key=lambda x: x["vol24"], reverse=True)
    uni = rows[:UNIVERSE]
    for i, t in enumerate(uni):
        t["cat"] = categorize(t["sym"], t["addr"], overrides)
        t["tracked"] = i < TRACKED
        for k in ("price", "mcap", "liq", "vol24", "d1"):
            t[k] = round(t[k], 6 if k == "price" else 2)
    out = {"updated": datetime.date.today().isoformat(), "count": len(uni), "tokens": uni}
    json.dump(out, open(D / "universe.json", "w"), separators=(",", ":"))
    cats = {t["addr"]: t["cat"] for t in uni if t["tracked"]}
    json.dump(cats, open(D / "cats.json", "w"), separators=(",", ":"))
    return out

def _check():
    assert categorize("tsTON", "x", {}) == "staking"
    assert categorize("USD₮", "x", {}) == "stable"
    assert categorize("MTONGA", "x", {}) == "meme"
    assert categorize("STON", "S", {"S": "defi"}) == "defi"
    print("universe self-check ok")

if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        _check()
    else:
        o = build()
        print(f"universe: {o['count']} tokens, {sum(t['tracked'] for t in o['tokens'])} tracked")
