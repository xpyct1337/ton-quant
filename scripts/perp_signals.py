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
    r"|\b(?:LONG|SHORT|BUY|SELL)\s+\$?([A-Z][A-Z0-9]{1,9})\b")  # LONG BTC
NUM = r"([0-9][0-9 ,]*(?:\.[0-9]+)?)"
ENTRY_PAT = re.compile(r"\b(?:entry|вход)\b[^0-9]{0,12}" + NUM, re.I)
SL_PAT = re.compile(r"\b(?:sl|stop(?:[\s-]*loss)?|стоп)\b[^0-9]{0,12}" + NUM, re.I)
TP_PAT = re.compile(r"\b(?:tp\d?|target[s]?|тейк|цел[иь])\b[^0-9]{0,12}" + NUM, re.I)
LEV_PAT = re.compile(r"\b(\d{1,3})\s*[xх]\b|\b[xх]\s*(\d{1,3})\b", re.I)

_num = lambda s: float(s.replace(" ", "").replace(",", ""))


def parse_signal(text):
    """Signal dict or None when the message has no coin+side pair."""
    if not text:
        return None
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
    out = {"coin": coin, "side": side}
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
    assert s == {"coin": "BTC", "side": "long", "entry": 65000.0,
                 "sl": 63500.0, "tps": [66000.0, 67500.0], "lev": 10}, s
    s = parse_signal("$SOL short 📉 entry 145.2 targets 140/136 stop 150 x5")
    assert s["coin"] == "SOL" and s["side"] == "short" and s["entry"] == 145.2
    assert s["tps"] == [140.0, 136.0] and s["sl"] == 150.0 and s["lev"] == 5, s
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
