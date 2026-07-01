#!/usr/bin/env python3
"""Social collector: ticker mentions from PUBLIC Telegram channel previews.

t.me/s/<channel> serves the last ~20 messages as HTML with no auth — enough for a
daily mention-count sample per tracked token. Channels live in
data/social_channels.json (Igor curates the list; TON memecoin channels belong there).

Precision over recall: only cashtag forms ($SYM / #SYM) count as a mention — many
tracked syms are common words (NOT, COIN, GM, DOGS...) and bare-word matching would
be noise. Velocity/divergence signals come later desk-side from the accumulated
daily history (mention_velocity = d(mentions)/dt; price-vs-mentions divergence).

Writes data/social/<date>.json keyed by token ADDR (merge-ready for desk load_aux).
Non-fatal workflow step. stdlib only.
"""
import json, os, re, time, datetime, urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Accept": "text/html"}


def fetch_channel(slug):
    req = urllib.request.Request(f"https://t.me/s/{slug}", headers=UA)
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    msgs = re.findall(r'tgme_widget_message_text[^>]*>(.*?)</div>', html, re.S)
    return [re.sub(r"<[^>]+>", " ", m) for m in msgs]


def count_mentions(texts, syms):
    """{sym: n} counting only cashtag forms ($SYM/#SYM), case-insensitive."""
    blob = " ".join(texts)
    out = {}
    for sym in syms:
        pat = re.compile(r"[$#]" + re.escape(sym) + r"\b", re.I)
        n = len(pat.findall(blob))
        if n:
            out[sym] = n
    return out


def main():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    cfg = json.load(open("data/social_channels.json"))
    channels = cfg.get("channels") or []
    uni = json.load(open("data/universe.json"))
    sym2addr = {t["sym"]: t["addr"] for t in uni["tokens"] if t.get("tracked")}
    texts, ok = [], 0
    for ch in channels:
        try:
            texts += fetch_channel(ch)
            ok += 1
        except Exception:
            pass
        time.sleep(1.0)
    mentions = count_mentions(texts, sym2addr)
    out = {"date": today, "channels_ok": ok, "msgs": len(texts),
           "tokens": {sym2addr[s]: {"mentions": n} for s, n in mentions.items()}}
    os.makedirs("data/social", exist_ok=True)
    json.dump(out, open(f"data/social/{today}.json", "w"), separators=(",", ":"))
    json.dump(out, open("data/social.json", "w"), separators=(",", ":"))
    print(f"social {today}: {ok}/{len(channels)} channels, {len(texts)} msgs, "
          f"{sum(mentions.values())} mentions across {len(mentions)} tokens")


if __name__ == "__main__":
    if os.environ.get("SOCIAL_SELFTEST"):
        texts = ["Buy $REDO now!! $redo to the moon", "This is not about tokens", "#UTYA breakout"]
        m = count_mentions(texts, ["REDO", "NOT", "UTYA"])
        assert m == {"REDO": 2, "UTYA": 1}, m       # bare word "not" must NOT count
        print("selftest OK", m)
    else:
        main()
