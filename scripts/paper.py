import json, os, time, datetime, urllib.request

KEY = "AEUCH5S5SBNE64AAAAAMCL5S6MOL6AFR42PEXAR3OL2K2VJTQS77IQCN7I3O54EQK76ZIFA"
START_CASH = 1000.0
POS_SIZE = 100.0
MAX_OPEN = 5
FEE = 0.003          # DEX fee per leg
TP, SL, MAX_DAYS = 0.20, -0.10, 3

def get(url, ton=False):
    h = {"Accept": "application/json", "User-Agent": "tonquant-paper"}
    if ton:
        h["Authorization"] = "Bearer " + KEY
    for i in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30))
        except Exception:
            if i == 3:
                raise
            time.sleep(2 * (i + 1))

def impact(liq_usd, size):
    q = max(liq_usd / 2.0, 1.0)
    return ((q + size) / q) ** 2 - 1

def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default

def main():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    snap = load("data/snapshots/%s.json" % today, None)
    if not snap:
        idx = load("data/index.json", {"dates": []})
        if not idx["dates"]:
            print("no snapshots yet"); return
        snap = load("data/snapshots/%s.json" % idx["dates"][-1], None)
    cats = load("data/cats.json", {})
    state = load("data/paper/state.json", {"cash": START_CASH, "positions": [], "trades": [], "equity": [], "wash_ban": {}})

    toks = snap["tokens"]
    still = []
    for p in state["positions"]:
        t = toks.get(p["addr"])
        cur = (t or {}).get("price")
        p["days"] += 1
        if not cur:
            still.append(p); continue
        liq = (t or {}).get("tvl", 0) or 0
        out_mult = 1 - min(impact(liq, POS_SIZE), 0.5) - FEE
        ret = cur / p["entry_eff"] - 1
        reason = None
        if ret >= TP: reason = "tp"
        elif ret <= SL: reason = "sl"
        elif p["days"] >= MAX_DAYS: reason = "time"
        if reason:
            proceeds = p["qty"] * cur * out_mult
            state["cash"] += proceeds
            state["trades"].append({"addr": p["addr"], "sym": p["sym"], "signal": p["signal"],
                "opened": p["opened"], "closed": today, "entry": p["entry_eff"], "exit": cur,
                "pnl": round(proceeds - POS_SIZE, 2), "ret": round(ret * 100, 2), "reason": reason})
        else:
            still.append(p)
    state["positions"] = still

    sigs = []
    for a, t in toks.items():
        if "error" in t or not t.get("price"): continue
        cat = cats.get(a, "meme")
        if cat in ("stable", "staking"): continue
        vol, tvl = t.get("vol24", 0) or 0, t.get("tvl", 0) or 0
        buys, sells = t.get("buys", 0), t.get("sells", 0)
        if tvl < 20000: continue
        if tvl > 0 and vol / tvl > 3:
            state["wash_ban"][a] = today
        ban = state["wash_ban"].get(a)
        if ban and (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(ban)).days < 7:
            continue
        dates = load("data/index.json", {"dates": []})["dates"]
        prev = None
        if len(dates) >= 2:
            prev_snap = load("data/snapshots/%s.json" % dates[-2], {"tokens": {}})
            prev = (prev_snap["tokens"].get(a) or {}).get("price")
        d24 = (t["price"] / prev - 1) * 100 if prev else None
        flat = d24 is not None and abs(d24) < 2
        if buys + sells > 50 and sells > buys * 1.5 and flat:
            sigs.append((a, t, "hidden_buyer", 2.0))
        if d24 is not None and d24 > 8:
            sigs.append((a, t, "momentum", 1.0))
    open_addrs = {p["addr"] for p in state["positions"]}
    sigs.sort(key=lambda x: -x[3])
    for a, t, sig, _w in sigs:
        if len(state["positions"]) >= MAX_OPEN: break
        if a in open_addrs or state["cash"] < POS_SIZE: continue
        liq = t.get("tvl", 0) or 0
        entry_eff = t["price"] * (1 + min(impact(liq, POS_SIZE), 0.5) + FEE)
        qty = POS_SIZE / entry_eff
        state["cash"] -= POS_SIZE
        state["positions"].append({"addr": a, "sym": t["sym"], "signal": sig, "opened": today,
            "entry_eff": entry_eff, "qty": qty, "days": 0})
        open_addrs.add(a)

    mtm = state["cash"]
    for p in state["positions"]:
        cur = (toks.get(p["addr"]) or {}).get("price") or p["entry_eff"]
        mtm += p["qty"] * cur
    if not state["equity"] or state["equity"][-1]["d"] != today:
        state["equity"].append({"d": today, "v": round(mtm, 2)})
    else:
        state["equity"][-1]["v"] = round(mtm, 2)

    os.makedirs("data/paper", exist_ok=True)
    with open("data/paper/state.json", "w") as f:
        json.dump(state, f, separators=(",", ":"))
    print("paper:", today, "equity", round(mtm, 2), "cash", round(state["cash"], 2),
          "open", len(state["positions"]), "closed-total", len(state["trades"]))

if __name__ == "__main__":
    main()
