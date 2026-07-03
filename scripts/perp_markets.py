#!/usr/bin/env python3
"""Hyperliquid perp-market snapshot for the /perps/ page fallback.

Прямой info-API Hyperliquid (api.hyperliquid.xyz) гео-блокируется на уровне
CloudFront в ряде регионов, поэтому браузер пользователя может не достучаться
до него, хотя raw.githubusercontent.com доступен. Этот коллектор дёргает API
с раннера GitHub Actions и сохраняет сырые [meta, assetCtxs] + свечи фокусной
монеты — страница использует файл, когда живой запрос падает.

Writes data/perp_markets.json:
  { "updated": <ms>, "meta": {...}, "ctxs": [...], "candles": {"<COIN>": [closes]} }

Selftest (no network): PERP_MARKETS_SELFTEST=1 python scripts/perp_markets.py
"""
import json, os, sys, time, urllib.request

API = "https://api.hyperliquid.xyz/info"
OUT = "data/perp_markets.json"
FOCUS = os.environ.get("PERP_FOCUS", "TON")


def info(body):
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def focus_closes(meta, coin):
    """1h closes for the last 7 days, [] when the coin is absent/delisted."""
    listed = any(u.get("name") == coin and not u.get("isDelisted")
                 for u in meta.get("universe", []))
    if not listed:
        return []
    end = int(time.time() * 1000)
    candles = info({"type": "candleSnapshot",
                    "req": {"coin": coin, "interval": "1h",
                            "startTime": end - 7 * 86400 * 1000, "endTime": end}})
    return [float(k["c"]) for k in (candles or []) if "c" in k]


def collect():
    meta, ctxs = info({"type": "metaAndAssetCtxs"})
    if not meta.get("universe") or not ctxs:
        raise SystemExit("empty metaAndAssetCtxs — refusing to overwrite snapshot")
    return {"updated": int(time.time() * 1000), "meta": meta, "ctxs": ctxs,
            "candles": {FOCUS: focus_closes(meta, FOCUS)}}


def selftest():
    fake_meta = {"universe": [{"name": "TON", "isDelisted": True},
                              {"name": "BTC"}]}
    assert focus_closes.__code__  # smoke: module imports
    # delisted focus → no candle request, empty list
    assert focus_closes(fake_meta, "TON") == []
    print("selftest ok")


if __name__ == "__main__":
    if os.environ.get("PERP_MARKETS_SELFTEST"):
        selftest(); sys.exit(0)
    snap = collect()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(snap, f, separators=(",", ":"))
    n = len(snap["meta"]["universe"])
    print(f"wrote {OUT}: {n} markets, {len(snap['candles'][FOCUS])} focus candles")
