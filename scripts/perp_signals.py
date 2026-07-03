#!/usr/bin/env python3
"""Perp-signal collector: messages from the @perptools_ai_bot Telegram bot.

The bot has no public API and no t.me/s/ preview (bot chats are private), so this
reads YOUR OWN chat with the bot through a Telegram user session (Telethon MTProto).
Secrets: TG_API_ID / TG_API_HASH (my.telegram.org → API development tools) and
TG_SESSION (StringSession; generate once with `python scripts/perp_signals.py --login`).

Parsing is best-effort over free-form bot text: coin + side are required, entry/
targets/stop/leverage optional, raw text always kept so nothing is lost when the
bot changes format. Dedup by Telegram message id, rolling window of 200.

Writes data/perp_signals.json. Non-fatal: exits 0 (no-op) without secrets.
Selftest: PERP_SELFTEST=1 python scripts/perp_signals.py  (stdlib only).
"""
import json, os, re, sys, datetime

BOT = os.environ.get("PERP_BOT", "perptools_ai_bot")
OUT = "data/perp_signals.json"
KEEP = 200

SIDE_PAT = re.compile(
    r"\b(long|buy)\b|🟢|📈|\b(short|sell)\b|🔴|📉", re.I)
COIN_PAT = re.compile(
    r"\$([A-Z][A-Z0-9]{1,9})\b"                 # $BTC
    r"|\b([A-Z][A-Z0-9]{1,9})[/-](?:USDT?|USDC|PERP)\b"  # BTC/USDT, SOL-PERP
    r"|\b([A-Z][A-Z0-9]{1,9})(?:USDT|USDC|PERP)\b"       # BTCUSDT (binance-style)
    r"|#([A-Z][A-Z0-9]{1,9})\b"                          # #BTC
    r"|\b(?:LONG|SHORT|BUY|SELL)\s+\$?#?([A-Z][A-Z0-9]{1,9})\b"  # LONG BTC
    r"|\b(?:COIN|PAIR|TICKER|МОНЕТА|ПАРА)\s*[:\-]?\s*\$?#?([A-Z][A-Z0-9]{1,9})\b")  # Coin: BTC
NUM = r"([0-9][0-9 ,]*(?:\.[0-9]+)?)"
ENTRY_PAT = re.compile(r"\b(?:entry|вход)\b[^0-9]{0,12}" + NUM, re.I)
SL_PAT = re.compile(r"\b(?:sl|stop(?:[\s-]*loss)?|стоп)\b[^0-9]{0,12}" + NUM, re.I)
TP_PAT = re.compile(r"\b(?:tp\d?|target[s]?|тейк|цел[иь])\b[^0-9]{0,12}" + NUM, re.I)
LEV_PAT = re.compile(r"\b(\d{1,3})\s*[xх]\b|\b[xх]\s*(\d{1,3})\b", re.I)

# The bot mostly posts market ALERTS, not trade calls, e.g.
# "📊 Volume Spike Detected\n\nLTC volume jumped +58.5% over the last 60 minutes".
# Coin stays case-sensitive uppercase so "The volume jumped 5%" can't match.
ALERT_PAT = re.compile(
    r"\b([A-Z][A-Z0-9]{1,9})\s+(volume|open interest|price|funding)\s+"
    r"(jumped|spiked|surged|dropped|fell)\s*([+\-]?\d+(?:\.\d+)?)\s*%")
ALERT_KIND = {"volume": "vol_spike", "open interest": "oi_spike",
              "price": "price_spike", "funding": "funding_spike"}
ALERT_WIN = re.compile(r"last\s+(\d+)\s*(minute|min|hour|h)", re.I)

_num = lambda s: float(s.replace(" ", "").replace(",", ""))


def parse_signal(text):
    """Signal dict or None when the message is neither an alert nor a trade call."""
    if not text:
        return None
    if (a := ALERT_PAT.search(text)):
        coin, metric, verb, pct = a.groups()
        pct = float(pct)
        if verb in ("dropped", "fell") and pct > 0:
            pct = -pct
        out = {"coin": coin, "kind": ALERT_KIND[metric], "pct": pct}
        if (w := ALERT_WIN.search(text)):
            out["win"] = int(w.group(1)) * (60 if w.group(2).lower().startswith("h") else 1)
        return out
    m = SIDE_PAT.search(text)
    if not m:
        return None
    side = "long" if (m.group(1) or m.group(0) in ("🟢", "📈")) else "short"
    c = COIN_PAT.search(text.upper())
    if not c:
        return None
    coin = next(g for g in c.groups() if g)
    if coin in ("USDT", "USD", "USDC", "PERP", "LONG", "SHORT"):
        return None
    out = {"coin": coin, "kind": "trade", "side": side}
    if (e := ENTRY_PAT.search(text)):
        out["entry"] = _num(e.group(1))
    if (s := SL_PAT.search(text)):
        out["sl"] = _num(s.group(1))
    # TP labels first; fall back to slash-separated list after "targets 140/136"
    tps = [_num(x) for x in TP_PAT.findall(text)]
    if len(tps) == 1 and (extra := re.search(TP_PAT.pattern + r"(?:\s*/\s*" + NUM + r")+", text, re.I)):
        tps += [_num(x) for x in re.findall(r"/\s*" + NUM, extra.group(0))]
    if tps:
        out["tps"] = tps
    if (l := LEV_PAT.search(text)):
        out["lev"] = int(l.group(1) or l.group(2))
    return out


def collect(api_id, api_hash, session):
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    with TelegramClient(StringSession(session), api_id, api_hash) as client:
        return [(m.id, m.date, m.message)
                for m in client.iter_messages(BOT, limit=100) if m.message]


def merge(prev, msgs):
    seen = {s["id"]: s for s in prev.get("signals", [])}
    parsed = 0
    for mid, date, text in msgs:
        if mid in seen:
            continue
        sig = parse_signal(text)
        if not sig:
            continue
        seen[mid] = {"id": mid, "ts": int(date.timestamp()), **sig,
                     "raw": text[:500]}
        parsed += 1
    signals = sorted(seen.values(), key=lambda s: -s["ts"])[:KEEP]
    return signals, parsed


def main():
    api_id, api_hash = os.environ.get("TG_API_ID"), os.environ.get("TG_API_HASH")
    session = os.environ.get("TG_SESSION")
    if not (api_id and api_hash and session):
        print("perp_signals: TG_API_ID/TG_API_HASH/TG_SESSION not set, skipping")
        return
    msgs = collect(int(api_id), api_hash, session)
    prev = json.load(open(OUT)) if os.path.exists(OUT) else {}
    signals, parsed = merge(prev, msgs)
    out = {"updated": datetime.datetime.now(datetime.timezone.utc)
           .strftime("%Y-%m-%dT%H:%M:%SZ"), "bot": BOT, "signals": signals}
    json.dump(out, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    print(f"perp_signals: {len(msgs)} msgs read, {parsed} new parsed, "
          f"{len(signals)} kept")
    if msgs and not signals:
        # nothing ever parsed: show truncated samples so the format mismatch
        # is debuggable from the workflow log (it's my own chat with the bot)
        for _, _, text in msgs[:3]:
            print("  unparsed sample:", text[:120].replace("\n", " | "))


def login():
    """One-time interactive login → prints the StringSession for the TG_SESSION secret."""
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    api_id = int(input("api_id (my.telegram.org): "))
    api_hash = input("api_hash: ").strip()
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        print("\nTG_SESSION (add as a repo secret, do NOT commit):\n")
        print(client.session.save())


def selftest():
    s = parse_signal("🟢 LONG BTC/USDT\nEntry: 65 000\nTP1: 66000 TP2: 67500\n"
                     "SL: 63500\nLeverage: 10x")
    assert s == {"coin": "BTC", "kind": "trade", "side": "long", "entry": 65000.0,
                 "sl": 63500.0, "tps": [66000.0, 67500.0], "lev": 10}, s
    s = parse_signal("$SOL short 📉 entry 145.2 targets 140/136 stop 150 x5")
    assert s["coin"] == "SOL" and s["side"] == "short" and s["entry"] == 145.2
    assert s["tps"] == [140.0, 136.0] and s["sl"] == 150.0 and s["lev"] == 5, s
    s = parse_signal("📈 BTCUSDT\nEntry: 65000")            # binance-style concat pair
    assert s["coin"] == "BTC" and s["side"] == "long" and s["entry"] == 65000.0, s
    s = parse_signal("Coin: TON\nDirection: SHORT\nstop 3.1")  # labeled format
    assert s == {"coin": "TON", "kind": "trade", "side": "short", "sl": 3.1}, s
    # alert formats actually posted by @perptools_ai_bot (from CI log samples)
    s = parse_signal("📊 Volume Spike Detected\n\nLTC volume jumped +58.5% over the last 60 minutes")
    assert s == {"coin": "LTC", "kind": "vol_spike", "pct": 58.5, "win": 60}, s
    s = parse_signal("📈 OI Spike Detected\n\nLIT open interest jumped +89.1% over the last 60 minutes")
    assert s == {"coin": "LIT", "kind": "oi_spike", "pct": 89.1, "win": 60}, s
    s = parse_signal("ETH price dropped 4.2% over the last 2 hours")
    assert s == {"coin": "ETH", "kind": "price_spike", "pct": -4.2, "win": 120}, s
    assert parse_signal("🏆 Top Agents — Last 24h\n#1 Alessandro\n├ PnL (24h): +21.51%\n└ AUM: $442.62") is None
    s = parse_signal("#ETH long entry 2500")                  # hashtag ticker
    assert s["coin"] == "ETH" and s["side"] == "long", s
    assert parse_signal("gm, market update: BTC dominance rising") is None
    assert parse_signal("LONG USDT") is None      # quote-only, not a coin
    assert parse_signal("") is None
    sigs, n = merge({"signals": [{"id": 1, "ts": 5, "coin": "X", "side": "long"}]},
                    [(1, FakeDate(9), "LONG $ETH"), (2, FakeDate(9), "SHORT $TON sl 2.9")])
    assert n == 1 and [x["id"] for x in sigs] == [2, 1], sigs  # dedup id=1, newest first
    print("selftest OK")


class FakeDate:
    def __init__(self, ts): self.ts = ts
    def timestamp(self): return self.ts


if __name__ == "__main__":
    if os.environ.get("PERP_SELFTEST"):
        selftest()
    elif "--login" in sys.argv:
        login()
    else:
        main()
