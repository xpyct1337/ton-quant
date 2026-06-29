#!/usr/bin/env python3
"""TON Quant v3.0 — vetted copy-trading book (Phase 3, working-product proof).

Compares copying ALL roster wallets vs only desk-vetted (copy_ok) ones, using only
existing data: copy signal = a roster wallet's FIRST entry into a token
(desk_features.first_entries); outcome = forward EXCESS return (desk_calibration).
Deterministic, no LLM, no new fetches. Cloud paper.py untouched.

Run from repo root. Self-check: python3 scripts/desk_copytrade.py --check
"""
import json, os, sys

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


def build_signals(first, roster_addrs, snaps, copyok, horizon):
    """One signal per (roster wallet, token first-entry) with a forward outcome."""
    sigs = []
    for w, toks in first.items():
        if w not in roster_addrs:
            continue
        for taddr, date in toks.items():
            ex = forward_excess(snaps, date, taddr, horizon)
            if ex is not None:
                sigs.append({"wallet": w, "token": taddr, "date": date,
                             "ex": ex, "copy_ok": w in copyok})
    return sigs


def build_copytrade():
    snaps = load_snaps()
    roster = {w["addr"] for w in (load("data/wallets.json", {}) or {}).get("roster", [])}
    verdicts = load("data/desk/verdicts.json", {}) or {}
    copyok = {w["addr"] for w in verdicts.get("wallets", []) if w.get("copy_ok")}
    sigs = build_signals(first_entries(), roster, snaps, copyok, HORIZON)
    allb = book_stats([s["ex"] for s in sigs])
    deskb = book_stats([s["ex"] for s in sigs if s["copy_ok"]])
    edge = round(deskb["avg"] - allb["avg"], 4)
    note = ("desk vetoed all wallets; copy_all avg %.4f avoided" % allb["avg"]
            if deskb["n"] == 0 else "")
    return {"horizon": HORIZON, "copyok_wallets": len(copyok),
            "copy_all": allb, "copy_desk": deskb, "edge": edge, "note": note}


def main():
    ct = build_copytrade()
    os.makedirs("data/desk", exist_ok=True)
    with open("data/desk/copytrade.json", "w") as f:
        json.dump(ct, f, ensure_ascii=False, indent=2)
    chk = json.load(open("data/desk/copytrade.json"))   # read-back
    print(f"copytrade: all n={chk['copy_all']['n']} avg={chk['copy_all']['avg']} | "
          f"desk n={chk['copy_desk']['n']} avg={chk['copy_desk']['avg']} | "
          f"edge={chk['edge']} {chk['note']}", flush=True)


def _check():
    ct = build_copytrade()
    for b in ("copy_all", "copy_desk"):
        assert set(ct[b]) == {"n", "avg", "win_rate", "total"}, f"bad book {b}"
        assert ct[b]["n"] >= 0
    assert ct["copy_desk"]["n"] <= ct["copy_all"]["n"], "desk book not subset"
    print("OK", {"all": ct["copy_all"], "desk": ct["copy_desk"], "edge": ct["edge"]})


if __name__ == "__main__":
    _check() if "--check" in sys.argv else main()
