#!/usr/bin/env python3
"""TON Quant v3.0 — point-in-time copy-trading paper baseline.

Compares copying ALL roster wallets vs only desk-vetted (copy_ok) ones, using only
existing data: copy signal = a desk-roster wallet's FIRST entry into a token on a
date with a saved desk verdict; outcome = forward EXCESS return
(desk_calibration). The roster and copy_ok flag are read from that same dated
verdict, never from today's desk output. Deterministic, no LLM, no new fetches.
Cloud paper.py untouched.

Run from repo root. Self-check: python3 scripts/desk_copytrade.py --check
"""
import glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_features import load, first_entries          # noqa: E402
from desk_calibration import load_snaps, forward_excess  # noqa: E402

HORIZON = 3   # short: dated wallet history is only a few days


def book_stats(exs):
    n = len(exs)
    if not n:
        return {"n": 0, "avg": 0.0, "win_rate": 0.0, "total": 0.0}
    wins = sum(1 for e in exs if e > 0)
    return {"n": n, "avg": round(sum(exs) / n, 4),
            "win_rate": round(100 * wins / n, 1), "total": round(sum(exs), 4)}


def dated_verdicts(path="data/desk/verdicts"):
    """{date: {roster, copyok}} from immutable daily desk journals."""
    out = {}
    for filename in sorted(glob.glob(os.path.join(path, "*.json"))):
        date = os.path.basename(filename)[:-5]
        verdict = load(filename, {}) or {}
        wallets = verdict.get("wallets", [])
        if verdict.get("date") != date or not isinstance(wallets, list):
            continue
        roster = {w.get("addr") for w in wallets if w.get("addr")}
        out[date] = {"roster": roster,
                     "copyok": {w.get("addr") for w in wallets if w.get("copy_ok") and w.get("addr")}}
    return out


def build_signals(first, snaps, verdicts_by_date, horizon):
    """One daily-close paper signal only when that date's verdict exists.

    ponytail: wallet history has day precision, so the paper entry is at the
    daily desk snapshot, not at the wallet's unknown intraday fill. Add event
    timestamps before making intraday execution claims.
    """
    sigs = []
    for w, toks in first.items():
        for taddr, date in toks.items():
            verdict = verdicts_by_date.get(date)
            if not verdict or w not in verdict["roster"]:
                continue
            ex = forward_excess(snaps, date, taddr, horizon)
            if ex is not None:
                sigs.append({"wallet": w, "token": taddr, "date": date,
                             "ex": ex, "copy_ok": w in verdict["copyok"]})
    return sigs


def build_copytrade():
    snaps = load_snaps()
    verdicts = dated_verdicts()
    sigs = build_signals(first_entries(), snaps, verdicts, HORIZON)
    allb = book_stats([s["ex"] for s in sigs])
    deskb = book_stats([s["ex"] for s in sigs if s["copy_ok"]])
    ready = bool(sigs) and bool(deskb["n"])
    if not sigs:
        note = "Нет закрытых входов с verdict той же даты: сравнение ещё не началось."
    elif not deskb["n"]:
        note = "На закрытых point-in-time входах desk не дал copy_ok; есть baseline/veto, но нет CopyDesk P&L для сравнения."
    else:
        note = "Point-in-time daily-close paper-сравнение; маленькая выборка не доказывает edge."
    return {"horizon": HORIZON, "point_in_time": True,
            "verdict_dates": len(verdicts), "covered_signals": len(sigs),
            "copyok_wallets": len({s["wallet"] for s in sigs if s["copy_ok"]}),
            "copy_all": allb, "copy_desk": deskb,
            "edge": round(deskb["avg"] - allb["avg"], 4) if ready else None,
            "comparison_ready": ready, "note": note}


def main():
    ct = build_copytrade()
    os.makedirs("data/desk", exist_ok=True)
    with open("data/desk/copytrade.json", "w", encoding="utf-8") as f:
        json.dump(ct, f, ensure_ascii=False, indent=2)
    with open("data/desk/copytrade.json", encoding="utf-8") as f:
        chk = json.load(f)                               # read-back
    print(f"copytrade: all n={chk['copy_all']['n']} avg={chk['copy_all']['avg']} | "
          f"comparison_ready={chk['comparison_ready']}", flush=True)


def _check():
    ct = build_copytrade()
    for b in ("copy_all", "copy_desk"):
        assert set(ct[b]) == {"n", "avg", "win_rate", "total"}, f"bad book {b}"
        assert ct[b]["n"] >= 0
    assert ct["copy_desk"]["n"] <= ct["copy_all"]["n"], "desk book not subset"
    assert ct["point_in_time"] is True
    assert ct["comparison_ready"] == bool(ct["copy_desk"]["n"] and ct["copy_all"]["n"])
    print("OK", {"all": ct["copy_all"], "desk": ct["copy_desk"], "edge": ct["edge"]})


if __name__ == "__main__":
    _check() if "--check" in sys.argv else main()
