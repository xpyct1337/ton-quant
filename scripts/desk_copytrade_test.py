#!/usr/bin/env python3
"""Plain-assert tests for desk_copytrade (run with python3)."""
import json
import tempfile
from pathlib import Path

import desk_copytrade as C


def test_book_stats():
    s = C.book_stats([0.1, -0.2, 0.3])
    assert s["n"] == 3 and abs(s["total"] - 0.2) < 1e-9
    assert s["win_rate"] == round(100 * 2 / 3, 1) and s["avg"] == round(0.2 / 3, 4)


def test_book_stats_empty():
    s = C.book_stats([])
    assert s == {"n": 0, "avg": 0.0, "win_rate": 0.0, "total": 0.0}


def test_build_signals_uses_verdict_from_entry_date():
    first = {"wA": {"TOK": "2026-02-01"}, "wB": {"BAD": "2026-02-01"}}
    snaps = {"2026-02-01": {"tokens": {"TOK": {"price": 1.0}, "BAD": {"price": 1.0}}},
             "2026-02-02": {"tokens": {"TOK": {"price": 1.2}, "BAD": {"price": 0.8}}}}
    verdicts = {"2026-02-01": {"roster": {"wA", "wB"}, "copyok": {"wA"}}}
    sigs = C.build_signals(first, snaps, verdicts, horizon=1)
    assert len(sigs) == 2                                   # both have forward data
    desk = [s for s in sigs if s["copy_ok"]]
    assert len(desk) == 1 and desk[0]["wallet"] == "wA"


def test_build_signals_rejects_missing_or_non_roster_verdict():
    first = {"wA": {"TOK": "2026-02-01"}, "wB": {"BAD": "2026-02-02"}}
    snaps = {"2026-02-01": {"tokens": {"TOK": {"price": 1.0}}},
             "2026-02-02": {"tokens": {"TOK": {"price": 1.1}, "BAD": {"price": 1.0}}},
             "2026-02-03": {"tokens": {"BAD": {"price": 1.1}}}}
    verdicts = {"2026-02-01": {"roster": {"wB"}, "copyok": {"wB"}}}
    assert C.build_signals(first, snaps, verdicts, horizon=1) == []


def test_dated_verdicts_uses_matching_journal_date_only():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        (path / "2026-02-01.json").write_text(json.dumps({"date": "2026-02-01", "wallets": [
            {"addr": "wA", "copy_ok": True}, {"addr": "wB", "copy_ok": False}]}), encoding="utf-8")
        (path / "2026-02-02.json").write_text(json.dumps({"date": "wrong", "wallets": []}), encoding="utf-8")
        verdicts = C.dated_verdicts(str(path))
        assert set(verdicts) == {"2026-02-01"}
        assert verdicts["2026-02-01"] == {"roster": {"wA", "wB"}, "copyok": {"wA"}}


if __name__ == "__main__":
    for n, fn in sorted(globals().items()):
        if n.startswith("test_"):
            fn(); print("ok", n)
    print("ALL PASS")
