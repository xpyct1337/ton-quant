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


def test_bundle_backtest_fails_closed_on_thin_buckets():
    snaps = {}
    for i in range(8):
        snaps[f"2026-01-{i + 1:02d}"] = {"tokens": {
            "A": {"price": 1.0 if i < 4 else 0.1},
            "B": {"price": 1.0 + i * 0.1},
        }}
    aux = {"2026-01-01": {"A": {"bundle": 0.3}, "B": {"bundle": 0.1}}}
    report = C.bundle_backtest(snaps, aux)
    assert report["available"] is False
    assert report["candidate"] is False
    assert report["high"] == {"n": 1, "avg": -0.8}
    assert report["low"] == {"n": 1, "avg": 0.8}


def test_bundle_confidence_requires_history():
    report = C.bundle_confidence({"2026-01-01": {"tokens": {}}})
    assert report == {"available": False, "passed": False, "reason": "insufficient_dates",
                      "matured_dates": 1, "required_dates": 6}


def test_momentum_confidence_requires_history():
    report = C.momentum_confidence({"2026-01-01": {"tokens": {}}})
    assert report == {"available": False, "passed": False, "reason": "insufficient_dates"}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
    print("ALL PASS")
