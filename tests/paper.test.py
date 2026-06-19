# paper.py signals-journal test (Alpha Engine stage 2)
# Run from repo root: python3 tests/paper.test.py
# Builds synthetic 2-day snapshots in a temp dir, runs scripts/paper.py, asserts journal schema.
import json, os, shutil, subprocess, sys, tempfile, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "scripts", "paper.py")

def run_paper(tmp):
    r = subprocess.run([sys.executable, PAPER], cwd=tmp, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + r.stdout
    return r

def main():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    yday = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    tmp = tempfile.mkdtemp(prefix="paper_test_")
    try:
        os.makedirs(os.path.join(tmp, "data", "snapshots"))
        prev = {"ton_usd": 3.0, "tokens": {
            "A": {"sym": "AAA", "price": 1.0, "holders": 20000, "tvl": 200000, "vol24": 50000, "buys": 10, "sells": 40, "mcap": 5e6},
            "B": {"sym": "BBB", "price": 1.0, "holders": 6000, "tvl": 80000, "vol24": 30000, "buys": 50, "sells": 50, "mcap": 2e6},
            "C": {"sym": "CCC", "price": 1.0, "holders": 1000, "tvl": 10000, "vol24": 50000, "buys": 30, "sells": 30, "mcap": 1e6},
            "D": {"sym": "DDD", "price": 1.0, "holders": 10000, "tvl": 100000, "vol24": 20000, "buys": 20, "sells": 20, "mcap": 3e6},
            "E": {"sym": "EEE", "price": 1.0, "holders": 8000, "tvl": 60000, "vol24": 10000, "buys": 70, "sells": 20, "mcap": 2e6},
            "F": {"sym": "FFF", "price": 1.0, "holders": 1000, "tvl": 24000, "vol24": 18000, "buys": 40, "sells": 40, "mcap": 8e5}}}
        cur = {"ton_usd": 3.1, "tokens": {
            "A": {"sym": "AAA", "price": 1.01, "holders": 20100, "tvl": 210000, "vol24": 60000, "buys": 20, "sells": 60, "mcap": 5e6},
            "B": {"sym": "BBB", "price": 1.12, "holders": 6100, "tvl": 85000, "vol24": 40000, "buys": 60, "sells": 40, "mcap": 2.2e6},
            "C": {"sym": "CCC", "price": 1.05, "holders": 1010, "tvl": 10000, "vol24": 50000, "buys": 30, "sells": 30, "mcap": 1e6},
            "D": {"sym": "DDD", "price": 0.95, "holders": 10300, "tvl": 100000, "vol24": 21000, "buys": 25, "sells": 25, "mcap": 2.8e6},
            "E": {"sym": "EEE", "price": 1.005, "holders": 8050, "tvl": 75000, "vol24": 12000, "buys": 75, "sells": 15, "mcap": 2e6},
            "F": {"sym": "FFF", "price": 1.13, "holders": 1010, "tvl": 25000, "vol24": 20000, "buys": 80, "sells": 10, "mcap": 8e5}}}
        json.dump(prev, open(os.path.join(tmp, "data", "snapshots", yday + ".json"), "w"))
        json.dump(cur, open(os.path.join(tmp, "data", "snapshots", today + ".json"), "w"))
        json.dump({"dates": [yday, today]}, open(os.path.join(tmp, "data", "index.json"), "w"))
        json.dump({a: "meme" for a in "ABCDEF"}, open(os.path.join(tmp, "data", "cats.json"), "w"))
        # two runs: second must be idempotent for signals index
        for _ in range(2):
            run_paper(tmp)

        j = json.load(open(os.path.join(tmp, "data", "signals", today + ".json")))
        sigs = {(s["addr"], s["sig"]) for s in j["signals"]}
        checks = [
            (("A", "hidden_buyer") in sigs, "hidden_buyer detected (sells>1.5x buys, flat)"),
            (("B", "momentum") in sigs, "momentum detected (+12%)"),
            (("D", "accum_div") in sigs, "accum_div detected (price -5%, holders +3%)"),
            (("D", "holders_surge") in sigs, "holders_surge detected (+300 holders)"),
            (("E", "liq_inflow") in sigs, "liq_inflow detected (TVL +25%, flat)"),
            (("E", "flow_imbalance") in sigs, "flow_imbalance detected (83% buys, 90 trades)"),
            ("C" not in {s["addr"] for s in j["signals"]}, "wash token excluded from signals"),
            ("C" in j["wash_banned"], "wash token listed in wash_banned"),
            (j["ton_usd"] == 3.1, "ton_usd recorded"),
            (j["date"] == today, "date recorded"),
            (all(all(k in s for k in ("addr", "sym", "sig", "w", "price", "tvl", "vol24", "holders", "d1")) for s in j["signals"]), "journal entry schema complete"),
            (all(s["price"] and s["price"] > 0 for s in j["signals"]), "price-at-signal present (backtest requires it)"),
        ]
        idx = json.load(open(os.path.join(tmp, "data", "signals", "index.json")))
        checks.append((idx["dates"] == [today], "signals index has exactly one entry after double run (idempotent)"))

        # ---- impact-aware sizing (feature #4) ----
        bots = json.load(open(os.path.join(tmp, "data", "paper", "bots.json")))["bots"]
        base_cap = {"cons": 100.0, "aggr": 150.0}
        curtoks = cur["tokens"]
        IMP_CAP = 0.01
        def cap_size(tvl):  # max $ keeping CPMM impact <= 1%
            return (tvl / 2.0) * ((1 + IMP_CAP) ** 0.5 - 1)
        all_pos = [(name, p) for name, b in bots.items() for p in b["positions"]]
        checks.append((len(all_pos) > 0, "paper bots opened positions"))
        checks.append((all("size" in p for _, p in all_pos), "every position carries per-trade size"))
        checks.append((all(0 < p["size"] <= base_cap[name] + 1e-6 for name, p in all_pos),
                       "size never exceeds base cap (risk only equal or lower)"))
        checks.append((all(p["size"] <= cap_size(curtoks[p["addr"]]["tvl"]) + 0.5 for _, p in all_pos),
                       "size respects 1% CPMM impact cap (per pool depth)"))
        # F is a thin pool (tvl 25k) -> aggr must size it DOWN well below the $150 base
        fpos = [p for name, b in bots.items() if name == "aggr" for p in b["positions"] if p["addr"] == "F"]
        checks.append((len(fpos) == 1 and fpos[0]["size"] < 100,
                       "thin pool F sized down (<$100) vs $150 base"))
        # deep pool A (tvl 210k) -> cons keeps full $100 base (impact non-binding)
        apos = [p for name, b in bots.items() if name == "cons" for p in b["positions"] if p["addr"] == "A"]
        checks.append((len(apos) == 1 and abs(apos[0]["size"] - 100.0) < 1e-6,
                       "deep pool A keeps full base size (sizing non-binding)"))

        # ---- MIN_EFF_W noise filter ----
        # Inject scores.json marking hidden_buyer + momentum as noise (mult=0.3)
        # hidden_buyer w=3.0 * 0.3 = 0.9 < 1.0 -> blocked
        # momentum    w=1.0 * 0.3 = 0.3 < 1.0 -> blocked
        noise_scores = {"per_sig": {
            "hidden_buyer": {"verdict": "noise", "h1": {}, "h3": {}, "h7": {}},
            "momentum":     {"verdict": "noise", "h1": {}, "h3": {}, "h7": {}}
        }}
        os.makedirs(os.path.join(tmp, "data", "signals"), exist_ok=True)
        with open(os.path.join(tmp, "data", "signals", "scores.json"), "w") as f:
            json.dump(noise_scores, f)
        # fresh bots state
        bots_path = os.path.join(tmp, "data", "paper", "bots.json")
        os.remove(bots_path)
        run_paper(tmp)
        bots_noise = json.load(open(bots_path))["bots"]
        cons_pos = [p["signal"] for p in bots_noise["cons"]["positions"]]
        aggr_pos = [p["signal"] for p in bots_noise["aggr"]["positions"]]
        checks.append(("hidden_buyer" not in cons_pos, "cons skips hidden_buyer when noise-suppressed (eff_w 0.9 < 1.0)"))
        checks.append(("momentum" not in aggr_pos, "aggr skips momentum when noise-suppressed (eff_w 0.3 < 1.0)"))
        # accum_div w=2.8 * 1.0 (collecting default) = 2.8 >= 1.0 -> still allowed for aggr
        checks.append(("accum_div" in aggr_pos or "holders_surge" in aggr_pos or len(aggr_pos) == 0,
                       "aggr can still open non-noise signals (accum/holders_surge) or no eligible ones"))

        failed = 0
        for ok, label in checks:
            print(("PASS" if ok else "FAIL"), "-", label)
            failed += 0 if ok else 1
        print("\n%d/%d passed" % (len(checks) - failed, len(checks)))
        sys.exit(1 if failed else 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
