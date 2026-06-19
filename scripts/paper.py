import json, os, datetime
from score import load

START_CASH = 1000.0
FEE = 0.003
IMPACT_CAP = 0.01
TURN_REF = 0.5
MIN_VSCALE = 0.3
MIN_POS = 25.0
MIN_EFF_W = 1.0  # skip entries if noise-adjusted priority drops below this

BOTS = {
    "cons": {"pos": 100.0, "max_open": 3, "tp": 0.15, "sl": -0.07, "max_days": 5,
             "min_tvl": 50000, "min_holders": 5000, "min_liq_ratio": 0.02,
             "signals": ["hidden_buyer", "holders_surge", "accum_div", "liq_inflow"]},
    "aggr": {"pos": 150.0, "max_open": 6, "tp": 0.30, "sl": -0.12, "max_days": 3,
             "min_tvl": 20000, "min_holders": 500, "min_liq_ratio": 0.0,
             "signals": ["hidden_buyer", "holders_surge", "accum_div", "liq_inflow",
                          "momentum", "breakout", "dip_reversal", "flow_imbalance"]},
}

def impact(liq_usd, size):
    q = max(liq_usd / 2.0, 1.0)
    return ((q + size) / q) ** 2 - 1

def position_size(cfg, t):
    base = cfg["pos"]
    tvl = t.get("tvl", 0) or 0
    if tvl <= 0:
        return 0.0
    impact_cap = (tvl / 2.0) * ((1 + IMPACT_CAP) ** 0.5 - 1)
    turn = (t.get("vol24", 0) or 0) / tvl
    vscale = 1.0 if turn <= TURN_REF else max(MIN_VSCALE, TURN_REF / turn)
    size = min(base, impact_cap) * vscale
    return round(size, 2) if size >= MIN_POS else 0.0

# Multipliers applied to signal priority when verdict is known.
# Journal always records raw w; multiplier only affects entry ranking.
SCORE_MULTS = {"edge": 1.5, "neutral": 0.8, "noise": 0.3, "collecting": 1.0}

def load_score_mults():
    """Return {sig: mult} from data/signals/scores.json per_sig verdicts."""
    sc = load("data/signals/scores.json", {})
    out = {}
    for sig, agg in sc.get("per_sig", {}).items():
        verdict = agg.get("verdict", "collecting")
        out[sig] = SCORE_MULTS.get(verdict, 1.0)
    return out

def pct(cur, prev):
    if prev is None or not prev:
        return None
    return (cur / prev - 1) * 100

def detect_signals(addr, t, hist, cats, wash_ban, today):
    out = []
    if "error" in t or not t.get("price"):
        return out
    if cats.get(addr, "meme") in ("stable", "staking"):
        return out
    vol, tvl = t.get("vol24", 0) or 0, t.get("tvl", 0) or 0
    buys, sells = t.get("buys", 0), t.get("sells", 0)
    prev = hist[-1] if hist else None
    d1 = pct(t["price"], (prev or {}).get("price"))
    dh = pct(t.get("holders", 0), (prev or {}).get("holders")) if prev else None
    dtvl = pct(tvl, (prev or {}).get("tvl")) if prev else None
    flat = d1 is not None and abs(d1) < 2
    if tvl > 0 and vol / tvl > 3:
        wash_ban[addr] = today
    ban = wash_ban.get(addr)
    if ban and (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(ban)).days < 7:
        return out
    if buys + sells > 50 and sells > buys * 1.5 and flat:
        out.append(("hidden_buyer", 3.0))
    if dh is not None and dh > 1.5 and (t.get("holders",0)-(prev or {}).get("holders",0)) > 100:
        out.append(("holders_surge", 2.5))
    if d1 is not None and dh is not None and d1 < -3 and dh > 0.5:
        out.append(("accum_div", 2.8))
    if dtvl is not None and dtvl > 20 and d1 is not None and abs(d1) < 3:
        out.append(("liq_inflow", 2.2))
    if d1 is not None and d1 > 8:
        out.append(("momentum", 1.0))
    if len(hist) >= 6:
        past_prices = [h.get("price") for h in hist if h.get("price")]
        past_vols = [h.get("vol24", 0) or 0 for h in hist]
        if past_prices and t["price"] > max(past_prices) * 1.02 and past_vols and vol > 2 * (sum(past_vols) / len(past_vols)):
            out.append(("breakout", 1.8))
    if d1 is not None and d1 < -12 and t.get("holders", 0) > 10000 and tvl > 100000:
        out.append(("dip_reversal", 1.5))
    if buys + sells >= 80 and buys / max(buys + sells, 1) >= 0.65:
        out.append(("flow_imbalance", 1.2))
    return out

def run_bot(name, cfg, bot, toks, sig_map, prev_map, today, score_mults=None):
    still = []
    for p in bot["positions"]:
        t = toks.get(p["addr"])
        cur = (t or {}).get("price")
        p["days"] += 1
        if not cur:
            still.append(p); continue
        tvl = (t or {}).get("tvl", 0) or 0
        dtvl = pct(tvl, (prev_map.get(p["addr"]) or {}).get("tvl"))
        ret = cur / p["entry_eff"] - 1
        reason = None
        if dtvl is not None and dtvl < -25: reason = "rug_exit"
        elif ret >= cfg["tp"]: reason = "tp"
        elif ret <= cfg["sl"]: reason = "sl"
        elif p["days"] >= cfg["max_days"]: reason = "time"
        if reason:
            size = p.get("size", cfg["pos"])
            out_mult = 1 - min(impact(tvl, size), 0.5) - FEE
            proceeds = p["qty"] * cur * out_mult
            bot["cash"] += proceeds
            bot["trades"].append({"addr": p["addr"], "sym": p["sym"], "signal": p["signal"],
                "opened": p["opened"], "closed": today, "entry": p["entry_eff"], "exit": cur,
                "size": round(size, 2),
                "pnl": round(proceeds - size, 2), "ret": round(ret * 100, 2), "reason": reason})
        else:
            still.append(p)
    bot["positions"] = still
    open_addrs = {p["addr"] for p in bot["positions"]}
    cands = []
    for addr, sigs in sig_map.items():
        t = toks[addr]
        tvl = t.get("tvl", 0) or 0
        mcap = t.get("mcap", 0) or 0
        if tvl < cfg["min_tvl"]: continue
        if t.get("holders", 0) < cfg["min_holders"]: continue
        if cfg["min_liq_ratio"] > 0 and mcap > 0 and tvl / mcap < cfg["min_liq_ratio"]: continue
        for sig, w in sigs:
            if sig in cfg["signals"]:
                mult = (score_mults or {}).get(sig, 1.0)
                cands.append((w * mult, addr, t, sig))
    cands.sort(key=lambda x: -x[0])
    for eff_w, addr, t, sig in cands:
        if len(bot["positions"]) >= cfg["max_open"]: break
        if eff_w < MIN_EFF_W: break  # sorted desc — rest also below threshold
        if addr in open_addrs: continue
        size = position_size(cfg, t)
        if size <= 0 or bot["cash"] < size: continue
        tvl = t.get("tvl", 0) or 0
        entry_eff = t["price"] * (1 + min(impact(tvl, size), 0.5) + FEE)
        qty = size / entry_eff
        bot["cash"] -= size
        bot["positions"].append({"addr": addr, "sym": t["sym"], "signal": sig, "opened": today,
                                  "entry_eff": entry_eff, "qty": qty, "size": size, "days": 0})
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
    idx = load("data/index.json", {"dates": []})
    dates = idx["dates"]
    if not dates:
        print("no snapshots"); return
    snap = load("data/snapshots/%s.json" % dates[-1], None)
    if not snap:
        print("snapshot missing"); return
    cats = load("data/cats.json", {})
    score_mults = load_score_mults()
    state = load("data/paper/bots.json", None)
    if state is None:
        state = {"wash_ban": {}, "bots": {n: {"cash": START_CASH, "positions": [], "trades": [], "equity": []} for n in BOTS}}
    toks = snap["tokens"]
    hist_snaps = [load("data/snapshots/%s.json" % d, {"tokens": {}})["tokens"] for d in dates[-8:-1]]
    prev_map = hist_snaps[-1] if hist_snaps else {}
    sig_map = {}
    journal = []
    for a, t in toks.items():
        hist = [hs.get(a) for hs in hist_snaps if hs.get(a)]
        sigs = detect_signals(a, t, hist, cats, state["wash_ban"], today)
        if sigs:
            sig_map[a] = sigs
            prev = prev_map.get(a) or {}
            d1 = pct(t["price"], prev.get("price"))
            for sig, w in sigs:
                journal.append({"addr": a, "sym": t.get("sym"), "sig": sig, "w": w,
                    "price": t.get("price"), "tvl": t.get("tvl"), "vol24": t.get("vol24"),
                    "holders": t.get("holders"),
                    "d1": round(d1, 2) if d1 is not None else None})
    summary = {}
    for name, cfg in BOTS.items():
        mtm = run_bot(name, cfg, state["bots"][name], toks, sig_map, prev_map, today, score_mults)
        summary[name] = round(mtm, 2)
    os.makedirs("data/signals", exist_ok=True)
    banned = sorted(a for a, d in state["wash_ban"].items()
                    if (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(d)).days < 7)
    with open("data/signals/%s.json" % today, "w") as f:
        json.dump({"date": today, "ton_usd": snap.get("ton_usd"),
                   "signals": journal, "wash_banned": banned}, f, separators=(",", ":"))
    sidx = load("data/signals/index.json", {"dates": []})
    if today not in sidx["dates"]:
        sidx["dates"].append(today)
        sidx["dates"].sort()
    with open("data/signals/index.json", "w") as f:
        json.dump(sidx, f, separators=(",", ":"))
    os.makedirs("data/paper", exist_ok=True)
    with open("data/paper/bots.json", "w") as f:
        json.dump(state, f, separators=(",", ":"))
    noise = [s for s, m in score_mults.items() if m < 1.0]
    print("paper2:", today, "signals:", {a: [s[0] for s in v] for a, v in sig_map.items()},
          "journal:", len(journal), "equity:", summary,
          "score_mults:", score_mults if score_mults else "none",
          "noise_blocked:", noise if noise else "none")

if __name__ == "__main__":
    main()
