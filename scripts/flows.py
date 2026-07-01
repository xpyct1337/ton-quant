#!/usr/bin/env python3
"""Trade-flow collector: per tracked token, sample recent DEX trades (GeckoTerminal,
free API the site already uses client-side) and reduce them to organic-vs-bot flow
metrics — the research doc's P1 "buyer concentration / unique buyers" signals:

  ubuyers    unique buyer wallets in the sample (organic interest proxy)
  buyer_conc top-10 buyers' share of buy volume (≈1 = a few bots wash the volume)
  buy_share  buy USD / total USD (direction of real flow, in dollars not tx counts)
  trades_n   sample size (guard: small n -> metrics are noise)

Writes data/flows/<date>.json + data/flows.json (latest). Non-fatal workflow step —
GeckoTerminal hiccups must never break the snapshot. Rate limit ~30/min -> paced.
conytail: stdlib only, top pool only (deepest pool carries the flow that matters).
"""
import json, os, time, datetime, urllib.request

GT = "https://api.geckoterminal.com/api/v2/networks/ton"
PACE = 2.2      # seconds between calls (limit ~30/min, 2 calls per token)


def get(url):
    h = {"Accept": "application/json", "User-Agent": "tonquant-flows"}
    for i in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30))
        except Exception:
            if i == 2:
                raise
            time.sleep(5 * (i + 1))


def flow_metrics(trades):
    """Reduce a GT trades list to the flow metrics above (pure, testable)."""
    buys, buy_usd, tot_usd = {}, 0.0, 0.0
    n = 0
    for t in trades:
        a = t.get("attributes") or {}
        usd = float(a.get("volume_in_usd") or 0)
        if usd <= 0:
            continue
        n += 1
        tot_usd += usd
        if a.get("kind") == "buy":
            buy_usd += usd
            w = a.get("tx_from_address") or "?"
            buys[w] = buys.get(w, 0.0) + usd
    out = {"trades_n": n, "ubuyers": len(buys)}
    if buy_usd > 0:
        top = sorted(buys.values(), reverse=True)[:10]
        out["buyer_conc"] = round(sum(top) / buy_usd, 4)
    if tot_usd > 0:
        out["buy_share"] = round(buy_usd / tot_usd, 4)
    return out


def main():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    uni = json.load(open("data/universe.json"))
    toks = [t["addr"] for t in uni["tokens"] if t.get("tracked")]
    out, errs = {}, 0
    for a in toks:
        try:
            pools = get(f"{GT}/tokens/{a}/pools")
            time.sleep(PACE)
            pool = ((pools.get("data") or [{}])[0].get("attributes") or {}).get("address")
            if not pool:
                continue
            tr = get(f"{GT}/pools/{pool}/trades")
            m = flow_metrics(tr.get("data") or [])
            if m["trades_n"]:
                out[a] = m
        except Exception:
            errs += 1
        time.sleep(PACE)
    if out:
        os.makedirs("data/flows", exist_ok=True)
        doc = {"date": today, "tokens": out}
        json.dump(doc, open(f"data/flows/{today}.json", "w"), separators=(",", ":"))
        json.dump(doc, open("data/flows.json", "w"), separators=(",", ":"))
    print(f"flows {today}: {len(out)}/{len(toks)} tokens, errors {errs}")


if __name__ == "__main__":
    if os.environ.get("FLOWS_SELFTEST"):
        # conytail self-check: metric math on inline data
        sample = [{"attributes": {"kind": "buy", "volume_in_usd": "90", "tx_from_address": "A"}},
                  {"attributes": {"kind": "buy", "volume_in_usd": "10", "tx_from_address": "B"}},
                  {"attributes": {"kind": "sell", "volume_in_usd": "100", "tx_from_address": "C"}}]
        m = flow_metrics(sample)
        assert m == {"trades_n": 3, "ubuyers": 2, "buyer_conc": 1.0, "buy_share": 0.5}, m
        print("selftest OK", m)
    else:
        main()
