#!/usr/bin/env python3
"""DEX new-token signal collector: public t.me/s/dexnewtoken channel.

t.me/s/<channel> serves the last ~20 messages as HTML with no auth — same
technique as scripts/social.py. Parses buy/sell alerts and new token listings.
Dedup by message hash, rolling window KEEP. Non-fatal: bad fetch → skip.

Writes data/dex_signals.json.
Selftest: DEX_SELFTEST=1 python scripts/dex_signals.py
"""
import html as htmllib
import json, os, re, sys, datetime, hashlib, urllib.request, time

CHANNEL = os.environ.get("DEX_CHANNEL", "dexnewtoken")
OUT = "data/dex_signals.json"
KEEP = 300
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
      "Accept": "text/html,*/*"}

# ── patterns ──────────────────────────────────────────────────────────────────
# TON raw address (0:hex…)
TON_ADDR = re.compile(r"0:[0-9a-fA-F]{64}")
# EQ… / UQ… Friendly TON addresses
TON_FRIENDLY = re.compile(r"\b(?:EQ|UQ)[A-Za-z0-9_-]{46}\b")
# ETH / BSC / EVM contract (0x…)
EVM_ADDR = re.compile(r"\b0x[0-9a-fA-F]{40}\b")

SIDE_PAT = re.compile(r"\b(buy|long|покупай|купи|call)\b|🟢|📈|🚀"
                       r"|\b(sell|short|продавай)\b|🔴|📉", re.I)
# $SYM or SYMBOL/USDT or «#SYM» or «токен SYM»
SYM_PAT = re.compile(
    r"\$([A-Z][A-Z0-9]{1,10})\b"
    r"|\b([A-Z][A-Z0-9]{1,10})[/-](?:USDT?|USDC|TON|BNB|ETH)\b"
    r"|#([A-Z][A-Z0-9]{1,10})\b", re.I)
NUM = r"([0-9][0-9 ,]*(?:\.[0-9]+)?)"
PRICE_PAT = re.compile(r"\b(?:price|цена|entry|вход)[^\d]{0,15}" + NUM, re.I)
TARGET_PAT = re.compile(r"\b(?:target|tp\d?|цель)[^\d]{0,15}" + NUM, re.I)


def fetch_channel(slug):
    req = urllib.request.Request(f"https://t.me/s/{slug}", headers=UA)
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    return parse_page(page)


def parse_page(page):
    # In the real t.me/s markup the message text comes BEFORE the date (the
    # <time datetime=…> lives in the footer), so slice the page per data-post
    # block and match text/date independently instead of one ordered regex.
    posts = list(re.finditer(r'tgme_widget_message\b[^>]*data-post="([^"]+)"', page))
    items = []
    for i, m in enumerate(posts):
        chunk = page[m.end():posts[i + 1].start() if i + 1 < len(posts) else len(page)]
        txt = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', chunk, re.S)
        if not txt:
            continue
        dt = re.search(r'<time[^>]*datetime="([^"]+)"', chunk)
        text = htmllib.unescape(re.sub(r"<[^>]+>", " ", txt.group(1))).strip()
        if text:
            items.append({"post_id": m.group(1), "dt": dt.group(1) if dt else "",
                          "text": text})
    return items


def parse_item(item):
    text = item["text"]
    sig = {"post_id": item["post_id"], "dt": item["dt"]}

    # side
    m = SIDE_PAT.search(text)
    if m:
        sig["side"] = "buy" if (m.group(1) or m.group(0) in ("🟢", "📈", "🚀")) else "sell"

    # coin symbol
    c = SYM_PAT.search(text.upper())
    if c:
        sym = next((g for g in c.groups() if g), None)
        if sym and sym not in ("USDT", "USDC", "TON", "BNB", "ETH", "USD"):
            sig["sym"] = sym

    # addresses
    if (a := TON_ADDR.search(text)):
        sig["addr"] = a.group(0)
    elif (a := TON_FRIENDLY.search(text)):
        sig["addr"] = a.group(0)
    elif (a := EVM_ADDR.search(text)):
        sig["addr"] = a.group(0)

    if (p := PRICE_PAT.search(text)):
        try: sig["price"] = float(p.group(1).replace(" ", "").replace(",", ""))
        except ValueError: pass
    if (t := TARGET_PAT.search(text)):
        try: sig["target"] = float(t.group(1).replace(" ", "").replace(",", ""))
        except ValueError: pass

    sig["raw"] = text[:600]
    # dedup key: hash of post_id (stable) or text
    sig["id"] = item["post_id"] or hashlib.md5(text.encode()).hexdigest()[:12]
    return sig


def merge(prev_signals, items):
    seen = {s["id"]: s for s in prev_signals}
    new_count = 0
    for item in items:
        sig = parse_item(item)
        if sig["id"] not in seen:
            seen[sig["id"]] = sig
            new_count += 1
    signals = sorted(seen.values(), key=lambda s: s.get("dt", ""), reverse=True)[:KEEP]
    return signals, new_count


def main():
    try:
        items = fetch_channel(CHANNEL)
    except Exception as e:
        print(f"dex_signals: fetch failed ({e}), skipping")
        return
    prev = json.load(open(OUT)) if os.path.exists(OUT) else {}
    signals, new_count = merge(prev.get("signals", []), items)
    out = {
        "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "channel": CHANNEL,
        "signals": signals,
    }
    os.makedirs("data", exist_ok=True)
    json.dump(out, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    print(f"dex_signals: {len(items)} msgs fetched, {new_count} new, {len(signals)} kept")


def selftest():
    # realistic t.me/s block order: bubble → text → footer with <time datetime>
    html_page = """
    <div class="tgme_widget_message text_not_supported_wrap js-widget_message"
         data-post="dexnewtoken/101" data-view="x">
      <div class="tgme_widget_message_bubble">
        <div class="tgme_widget_message_text js-message_text" dir="auto">
          &#036;AAA/USDT 🚀 price 0.5</div>
        <div class="tgme_widget_message_info">
          <a class="tgme_widget_message_date" href="https://t.me/dexnewtoken/101">
            <time datetime="2026-07-03T10:00:00+00:00" class="time">10:00</time></a>
        </div></div></div>
    <div class="tgme_widget_message" data-post="dexnewtoken/102">
      <div class="tgme_widget_message_bubble">
        <div class="tgme_widget_message_text js-message_text" dir="auto">sell #BBB</div>
        <a class="tgme_widget_message_date" href="x">
          <time datetime="2026-07-03T11:00:00+00:00">11:00</time></a>
      </div></div>"""
    parsed = parse_page(html_page)
    assert [p["post_id"] for p in parsed] == ["dexnewtoken/101", "dexnewtoken/102"], parsed
    assert parsed[0]["dt"] == "2026-07-03T10:00:00+00:00", parsed[0]
    assert parsed[0]["text"] == "$AAA/USDT 🚀 price 0.5", parsed[0]
    assert parsed[1]["dt"] == "2026-07-03T11:00:00+00:00", parsed[1]
    assert parsed[1]["text"] == "sell #BBB", parsed[1]

    items = [
        {"post_id": "dexnewtoken/1", "dt": "2026-07-03T10:00:00+00:00",
         "text": "🚀 New listing! $MYTOKEN/USDT on STON.fi\nEntry: 0.0012\nTarget: 0.002\nAddr: 0:" + "a"*64},
        {"post_id": "dexnewtoken/2", "dt": "2026-07-03T09:00:00+00:00",
         "text": "🔴 SELL #RUGCOIN — liquidity removed"},
        {"post_id": "dexnewtoken/3", "dt": "2026-07-03T08:00:00+00:00",
         "text": "market update, nothing to trade"},
    ]
    signals, n = merge([], items)
    assert n == 3, n
    assert signals[0]["side"] == "buy", signals[0]
    assert signals[0]["sym"] == "MYTOKEN", signals[0]
    assert signals[0]["price"] == 0.0012, signals[0]
    assert "addr" in signals[0], signals[0]
    assert signals[1]["side"] == "sell", signals[1]
    assert signals[1]["sym"] == "RUGCOIN", signals[1]
    # dedup
    signals2, n2 = merge(signals, items)
    assert n2 == 0, n2
    assert len(signals2) == 3
    print("selftest OK")


if __name__ == "__main__":
    if os.environ.get("DEX_SELFTEST"):
        selftest()
    else:
        main()
