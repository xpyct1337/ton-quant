import json, os, sys, datetime

START_CASH = 1000.0

# CEX-listed liquid majors: near-zero slippage, so no TVL/impact model like the
# TON bot. Just a flat taker fee per leg. ponytail: ignores depth entirely
# (ceiling: huge size would move thin alts; upgrade = pull order-book depth).
ALT = {"pos": 500.0, "max_open": 2, "tp": 0.20, "sl": -0.10, "max_days": 5, "fee": 0.001,
       "signals": ["breakout", "vol_spike", "momentum", "dip_reversal"]}


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def detect_signals(rec, hist):
    """Price/volume signals only — the on-chain accumulation signals the TON bot
    uses (hidden_buyer, holders_surge, ...) have no CEX equivalent. hist is the
    list of prior daily records (oldest->newest)."""
    out = []
    if "error" in rec or not rec.get("price"):
        return out
    price, vol = rec["price"], rec.get("vol24", 0) or 0
    chg = rec.get("chg24")
    prices = [h["price"] for h in hist if h.get("price")]
    vols = [h.get("vol24", 0) or 0 for h in hist]
    avg_vol = sum(vols) / len(vols) if vols else 0
    if len(prices) >= 6 and price > max(prices) * 1.02 and avg_vol and vol > 2 * avg_vol:
        out.append(("breakout", 2.5))
    if len(vols) >= 3 and avg_vol and vol > 3 * avg_vol and chg is not None and abs(chg) < 3:
        out.append(("vol_spike", 2.2))
    if chg is not None and chg > 8:
        out.append(("momentum", 1.5))
    if chg is not None and chg < -10:
        out.append(("dip_reversal", 1.5))
    return out


def run_bot(bot, toks, sig_map, today):
    cfg = ALT
    still = []
    for p in bot["positions"]:
        cur = (toks.get(p["addr"]) or {}).get("price")
        p["days"] += 1
        if not cur:
            still.append(p); continue
        ret = cur / p["entry_eff"] - 1
        reason = None
        if ret >= cfg["tp"]: reason = "tp"
        elif ret <= cfg["sl"]: reason = "sl"
        elif p["days"] >= cfg["max_days"]: reason = "time"
        if reason:
            size = p.get("size", cfg["pos"])
            proceeds = p["qty"] * cur * (1 - cfg["fee"])
            bot["cash"] += proceeds
            bot["trades"].append({"addr": p["addr"], "sym": p["sym"], "signal": p["signal"],
                "opened": p["opened"], "closed": today, "entry": p["entry_eff"], "exit": cur,
                "size": round(size, 2), "pnl": round(proceeds - size, 2),
                "ret": round(ret * 100, 2), "reason": reason})
        else:
            still.append(p)
    bot["positions"] = still
    open_addrs = {p["addr"] for p in bot["positions"]}
    cands = []
    for addr, sigs in sig_map.items():
        for sig, w in sigs:
            if sig in cfg["signals"]:
                cands.append((w, addr, toks[addr], sig))
    cands.sort(key=lambda x: -x[0])
    for w, addr, t, sig in cands:
        if len(bot["positions"]) >= cfg["max_open"]: break
        if addr in open_addrs: continue
        size = cfg["pos"]
        if bot["cash"] < size: continue
        entry_eff = t["price"] * (1 + cfg["fee"])
        bot["cash"] -= size
        bot["positions"].append({"addr": addr, "sym": t["sym"], "signal": sig, "opened": today,
                                 "entry_eff": entry_eff, "qty": size / entry_eff, "size": size, "days": 0})
        open_addrs.add(addr)
    mtm = bot["cash"]
    for p in bot["positions"]:
        cur = (toks.get(p["addr"]) or {}).get("price") or p["entry_eff"]
        mtm += p["qty"] * cur
    if not bot["equity"] or bot["equity"][-1]["d"] != today:
        bot["equity"].append({"d": today, "v": round(mtm, 2)})
    else:
        bot["equity"][-1]["v"] = round(mtm, 2)
    return mtm


def main():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    idx = load("data/alt/index.json", {"dates": []})
    dates = idx["dates"]
    if not dates:
        print("no alt snapshots"); return
    snap = load("data/alt/snapshots/%s.json" % dates[-1], None)
    if not snap:
        print("alt snapshot missing"); return
    toks = snap["tokens"]
    hist_snaps = [load("data/alt/snapshots/%s.json" % d, {"tokens": {}})["tokens"] for d in dates[-8:-1]]
    sig_map = {}
    for a, t in toks.items():
        hist = [hs.get(a) for hs in hist_snaps if hs.get(a)]
        sigs = detect_signals(t, hist)
        if sigs:
            sig_map[a] = sigs
    state = load("data/paper/altbots.json", None)
    if state is None:
        state = {"bots": {"alt": {"cash": START_CASH, "positions": [], "trades": [], "equity": []}}}
    mtm = run_bot(state["bots"]["alt"], toks, sig_map, today)
    os.makedirs("data/paper", exist_ok=True)
    with open("data/paper/altbots.json", "w") as f:
        json.dump(state, f, separators=(",", ":"))
    print("altpaper:", today, "signals:", {a: [s[0] for s in v] for a, v in sig_map.items()},
          "equity:", round(mtm, 2))


def _selfcheck():
    # breakout: today's price tops a 6-day base on >2x avg volume
    hist = [{"price": 10, "vol24": 100} for _ in range(6)]
    rec = {"price": 11, "vol24": 300, "chg24": 1}
    sigs = [s for s, _ in detect_signals(rec, hist)]
    assert "breakout" in sigs, sigs
    # momentum on a fresh coin with no history
    assert "momentum" in [s for s, _ in detect_signals({"price": 5, "vol24": 0, "chg24": 12}, [])]
    # dip_reversal
    assert "dip_reversal" in [s for s, _ in detect_signals({"price": 5, "vol24": 0, "chg24": -15}, [])]
    # one bot cycle: a momentum signal opens a position and records equity
    bot = {"cash": START_CASH, "positions": [], "trades": [], "equity": []}
    toks = {"x": {"sym": "X", "price": 100.0}}
    run_bot(bot, toks, {"x": [("momentum", 1.5)]}, "2026-01-01")
    assert len(bot["positions"]) == 1 and bot["equity"], bot
    # exit at take-profit next day
    run_bot(bot, {"x": {"sym": "X", "price": 130.0}}, {}, "2026-01-02")
    assert bot["trades"] and bot["trades"][-1]["reason"] == "tp", bot["trades"]
    print("altpaper selfcheck OK")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
