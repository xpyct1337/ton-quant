import json, os, glob, time, datetime, urllib.request

# Non-TON coins traded by the "alt" paper portfolio. CEX-listed / non-TON, so
# on-chain metrics (TVL, holders, buys/sells) don't exist — we only get price +
# 24h volume + 24h change from CoinGecko. Extend this map to add coins.
#   coingecko_id : display symbol
COINS = {
    "hyperliquid": "HYPE",
    "zcash": "ZEC",
}

# CoinGecko, not Binance/Bybit: those are geo-blocked from GitHub Actions (US)
# and from this sandbox. CoinGecko's public API is keyless and unblocked.
CG = "https://api.coingecko.com/api/v3/simple/price"


def get(url):
    h = {"Accept": "application/json", "User-Agent": "tonquant-altsnapshot"}
    for i in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30))
        except Exception:
            if i == 3:
                raise
            time.sleep(2 * (i + 1))


def main():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    ids = "%2C".join(COINS)
    url = "%s?ids=%s&vs_currencies=usd&include_24hr_vol=true&include_24hr_change=true" % (CG, ids)
    data = get(url)
    out = {"date": today, "ts": int(time.time()), "tokens": {}}
    for cid, sym in COINS.items():
        rec = {"sym": sym}
        d = data.get(cid)
        if d and d.get("usd"):
            rec["price"] = d.get("usd")
            rec["vol24"] = round(d.get("usd_24h_vol") or 0, 2)
            rec["chg24"] = round(d.get("usd_24h_change") or 0, 3)
        else:
            rec["error"] = "no price"
        out["tokens"][cid] = rec
    os.makedirs("data/alt/snapshots", exist_ok=True)
    with open("data/alt/snapshots/" + today + ".json", "w") as f:
        json.dump(out, f, separators=(",", ":"))
    dates = sorted(os.path.basename(p)[:-5] for p in glob.glob("data/alt/snapshots/*.json"))
    with open("data/alt/index.json", "w") as f:
        json.dump({"dates": dates, "coins": COINS}, f, separators=(",", ":"))
    print("altsnapshot", today, "coins:", len(out["tokens"]),
          "errors:", sum(1 for t in out["tokens"].values() if "error" in t))


if __name__ == "__main__":
    main()
