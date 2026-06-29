#!/usr/bin/env python3
"""Plain-assert tests for desk_copytrade (run with python3)."""
import desk_copytrade as C


def test_book_stats():
    s = C.book_stats([0.1, -0.2, 0.3])
    assert s["n"] == 3 and abs(s["total"] - 0.2) < 1e-9
    assert s["win_rate"] == round(100 * 2 / 3, 1) and s["avg"] == round(0.2 / 3, 4)


def test_book_stats_empty():
    s = C.book_stats([])
    assert s == {"n": 0, "avg": 0.0, "win_rate": 0.0, "total": 0.0}


def test_build_signals_filters_copyok():
    first = {"wA": {"TOK": "2026-02-01"}, "wB": {"BAD": "2026-02-01"}}
    snaps = {"2026-02-01": {"tokens": {"TOK": {"price": 1.0}, "BAD": {"price": 1.0}}},
             "2026-02-02": {"tokens": {"TOK": {"price": 1.2}, "BAD": {"price": 0.8}}}}
    sigs = C.build_signals(first, {"wA", "wB"}, snaps, {"wA"}, horizon=1)
    assert len(sigs) == 2                                   # both have forward data
    desk = [s for s in sigs if s["copy_ok"]]
    assert len(desk) == 1 and desk[0]["wallet"] == "wA"


if __name__ == "__main__":
    for n, fn in sorted(globals().items()):
        if n.startswith("test_"):
            fn(); print("ok", n)
    print("ALL PASS")
