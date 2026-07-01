import json, os, glob, time, datetime, urllib.request

KEY = "AEUCH5S5SBNE64AAAAAMCL5S6MOL6AFR42PEXAR3OL2K2VJTQS77IQCN7I3O54EQK76ZIFA"
TOKENS = {
 "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs": "USD₮",
 "EQC98_qAmNEptUtPc7W6xdHh_ZHrBUFpw5Ft_IzNU20QAJav": "tsTON",
 "EQA2kCVNwVsil2EM2mB0SkXytxCqQjS4mttjDpnXmwG9T6bO": "STON",
 "EQAvlWFDxGF2lXm67y4yzC17wYKD9A0guwPkMs1gOsM__NOT": "NOT",
 "EQAJ8uWd7EBqsmpSWaRdf_I-8R8-XHwh3gsNKhy-UrdrPcUo": "HMSTR",
 "EQCvxJy4eG8hyHBFsZ7eePxrRsUQSFE_jpptRAYBmcG_DOGS": "DOGS",
 "EQBaCgUwOoc6gHCNln_oJzb0mVs79YG7wYoavh-o1ItaneLA": "UTYA",
 "EQA1EIDrR33zgL21rwDIfGo7h4ETWieentUvg7jIT-3aP5GG": "FRT",
 "EQBlqsm144Dq6SjbPI4jjZvA1hqTIP3CvHovbIfW_t-SCALE": "DUST",
 "EQBZ_cafPyDr5KUTs0aNxh0ZTDhkpEZONmLJA2SNGlLm4Cko": "REDO",
 "EQBsosmcZrD6FHijA7qWGLw5wo_aH8UN435hi935jJ_STORM": "STORM",
 "EQC47093oX5Xhb0xuk2lCr2RhS8rj-vul61u4W2UH5ORmG_O": "GRM",
 "EQCuPm01HldiduQ55xaBF_1kaW_WAUy5DHey8suqzU_MAJOR": "MAJOR",
 "EQDNhy-nxYFgUqzfUzImBEP67JqsyMIcyk2S5_RwNNEYku0k": "stTON",
 "EQC7vuKEYLdC72YhUWt3AUVA-Oi66Q1DxTHXH7r6pXaV50j7": "Yoda",
 "EQBKRSNRkeP1-2jcg5T_f__0s5Hj-vrbfNLMQy8dnZs7xd_p": "CHERRY",
 "EQAtwo6qMNwtr0iTA9eKVZ32cuACFJ0VKd78GrBWOe83-X1P": "GROYP",
 "EQBynBO23ywHy_CgarY9NK9FTz0yDsG82PtcbSTQgGoXwiuA": "jUSDT",
 "EQDuGgqZU7_AEgiOwEe-abozIefuoairTWLOyd7c_f8GhzMf": "MTONGA",
 "EQACLXDwit01stiqK9FvYiJo15luVzfD5zU8uwDSq6JXxbP8": "SP",
 "EQDV0Q8euPPdsxHfaOQAmtdDrh3j5o_odMYIJM4nuiUO6t88": "SCAT",
 "EQC4Dx5Mqy9qhqHpH0cl_U8hejBnchNXZn_L0_Oj2zLY5B3P": "COIN",
 "EQD0vdSA_NedR9uvbgN9EikRX-suesDxGeFg69XQMavfLqIw": "BOLT",
 "EQBARQjzu8ZnTzJJMXlDqrnaZ-CH_nrV2XbzL28l6-p8xNo9": "GTA"
}

# conytail: universe.py owns the tracked set; the dict above is a fallback if it hasn't run yet.
try:
    _u = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "universe.json")))
    _tr = {t["addr"]: t["sym"] for t in _u["tokens"] if t.get("tracked")}
    if _tr:
        TOKENS = _tr
except Exception:
    pass

def get(url, ton=False):
    h = {"Accept": "application/json", "User-Agent": "tonquant-snapshot"}
    if ton:
        h["Authorization"] = "Bearer " + KEY
    for i in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30))
        except Exception as e:
            if i == 3:
                raise
            time.sleep(2 * (i + 1))

def main():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    out = {"date": today, "ts": int(time.time()), "tokens": {}}
    addrs = list(TOKENS)
    rates = {}
    for i in range(0, len(addrs), 10):
        chunk = "%2C".join(addrs[i:i + 10])
        rates.update(get("https://tonapi.io/v2/rates?tokens=" + chunk + "%2CTON&currencies=usd", ton=True).get("rates", {}))
        time.sleep(0.3)
    out["ton_usd"] = (rates.get("TON", {}).get("prices") or {}).get("USD")
    for a, sym in TOKENS.items():
        rec = {"sym": sym}
        try:
            j = get("https://tonapi.io/v2/jettons/" + a, ton=True)
            rec["holders"] = j.get("holders_count", 0)
            rec["supply"] = j.get("total_supply", "0")
            # deployer registry seed (same response, zero extra calls): admin address,
            # None once renounced. History accumulates -> repeat-offender scoring later.
            rec["admin"] = (j.get("admin") or {}).get("address")
            dec = int(j.get("metadata", {}).get("decimals", 9))
            r = rates.get(a, {})
            rec["price"] = (r.get("prices") or {}).get("USD")
            if rec["price"]:
                rec["mcap"] = rec["price"] * int(rec["supply"]) / 10 ** dec
            d = get("https://api.dexscreener.com/latest/dex/tokens/" + a)
            pairs = [p for p in (d.get("pairs") or []) if p.get("chainId") == "ton"]
            rec["tvl"] = round(sum(p.get("liquidity", {}).get("usd") or 0 for p in pairs), 2)
            rec["vol24"] = round(sum(p.get("volume", {}).get("h24") or 0 for p in pairs), 2)
            rec["buys"] = sum((p.get("txns", {}).get("h24") or {}).get("buys") or 0 for p in pairs)
            rec["sells"] = sum((p.get("txns", {}).get("h24") or {}).get("sells") or 0 for p in pairs)
            rec["pools"] = len(pairs)
            # pool-structure signals from the SAME pairs response (zero extra calls):
            # spread = cross-DEX price dispersion (manipulation/fragmentation),
            # top_pool = TVL share of the biggest pool (fragility), age_d = token age.
            liq = [p for p in pairs if p.get("baseToken", {}).get("address") == a
                   and (p.get("liquidity", {}).get("usd") or 0) > 5000
                   and (p.get("volume", {}).get("h24") or 0) > 100 and p.get("priceUsd")]
            if len(liq) >= 2:
                ps = [float(p["priceUsd"]) for p in liq]
                rec["spread"] = round((max(ps) - min(ps)) / min(ps) * 100, 3)
            if rec["tvl"] > 0:
                rec["top_pool"] = round(max(p.get("liquidity", {}).get("usd") or 0 for p in pairs) / rec["tvl"], 3)
            created = [p.get("pairCreatedAt") for p in pairs if p.get("pairCreatedAt")]
            if created:
                rec["age_d"] = int((time.time() * 1000 - min(created)) / 86400000)
        except Exception as e:
            rec["error"] = str(e)[:120]
        out["tokens"][a] = rec
        time.sleep(0.4)
    if os.environ.get("INTRADAY"):
        # second daily sample (intraday.yml, 15:10 UTC) -> separate dir so the daily
        # snapshot semantics (one 03:10 UTC slice/day, all return windows) stay intact.
        # Doubles time-series resolution for momentum features as history accumulates.
        os.makedirs("data/intraday", exist_ok=True)
        with open("data/intraday/" + today + ".json", "w") as f:
            json.dump(out, f, separators=(",", ":"))
        print("intraday", today, "tokens:", len(out["tokens"]), "errors:", sum(1 for t in out["tokens"].values() if "error" in t))
        return
    os.makedirs("data/snapshots", exist_ok=True)
    with open("data/snapshots/" + today + ".json", "w") as f:
        json.dump(out, f, separators=(",", ":"))
    dates = sorted(os.path.basename(p)[:-5] for p in glob.glob("data/snapshots/*.json"))
    with open("data/index.json", "w") as f:
        json.dump({"dates": dates, "tokens": TOKENS}, f, separators=(",", ":"))
    print("snapshot", today, "tokens:", len(out["tokens"]), "errors:", sum(1 for t in out["tokens"].values() if "error" in t))

if __name__ == "__main__":
    main()
