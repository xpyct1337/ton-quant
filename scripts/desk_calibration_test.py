#!/usr/bin/env python3
"""Plain-assert tests for desk_calibration (repo style, run with python3)."""
import desk_calibration as C


def test_forward_excess():
    # token A doubled (+1.0), token B flat (0.0); mean = +0.5
    snaps = {
        "2026-01-01": {"tokens": {"A": {"price": 1.0}, "B": {"price": 1.0}}},
        "2026-01-02": {"tokens": {"A": {"price": 2.0}, "B": {"price": 1.0}}},
    }
    assert abs(C.forward_excess(snaps, "2026-01-01", "A", 1) - 0.5) < 1e-9
    assert abs(C.forward_excess(snaps, "2026-01-01", "B", 1) + 0.5) < 1e-9


def test_forward_excess_missing_returns_none():
    snaps = {"2026-01-01": {"tokens": {"A": {"price": 1.0}}}}
    assert C.forward_excess(snaps, "2026-01-01", "A", 1) is None   # no +1d snapshot


def test_banned_as_of():
    wb = {"A": "2026-01-05"}
    assert C.banned_as_of(wb, "A", "2026-01-10") is True
    assert C.banned_as_of(wb, "A", "2026-01-01") is False
    assert C.banned_as_of(wb, "B", "2026-01-10") is False


def test_bucket_means_orders_high_worst():
    rows = [("high", -0.3), ("high", -0.1), ("low", 0.2), ("low", 0.4), ("med", 0.0)]
    m = C.bucket_means(rows)
    assert m["high"]["n"] == 2 and abs(m["high"]["avg"] + 0.2) < 1e-9
    assert abs(m["low"]["avg"] - 0.3) < 1e-9
    assert m["high"]["avg"] < m["low"]["avg"]   # signal works: high underperforms


def test_monotonic_gate_rejects_u_shape():
    buckets = {
        "low": {"n": 2, "avg": -0.1},
        "med": {"n": 2, "avg": 0.5},
        "high": {"n": 2, "avg": -0.2},
    }
    assert C.monotonic_separation(buckets) is False
    buckets["med"]["avg"] = -0.15
    assert C.monotonic_separation(buckets) is True


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
    print("ALL PASS")
