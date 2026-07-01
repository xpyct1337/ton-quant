#!/usr/bin/env python3
"""Plain-assert tests for desk_deployers (run with python3)."""
import desk_deployers as X


def _snaps():
    # DEV1 launched A (wash-banned) and B (healthy); DEV2 launched C (price collapse)
    snaps = {}
    for i in range(6):
        snaps[f"2026-06-{i+1:02d}"] = {"tokens": {
            "A": {"price": 1.0, "admin": "DEV1"},
            "B": {"price": 1.0 + i * 0.1, "admin": "DEV1"},
            "C": {"price": 1.0 if i < 3 else 0.05, "admin": "DEV2"},
        }}
    return snaps


def test_outcomes_and_registry():
    o = X.token_outcomes(_snaps(), wash_ban={"A"})
    assert o["A"]["rugged"] is True          # wash-banned
    assert o["B"]["rugged"] is False         # healthy
    assert o["C"]["rugged"] is True          # collapsed to 5% of peak
    r = X.build_registry(o)
    assert r["deployers"]["DEV1"] == {"tokens": 2, "rugged": 1, "rug_rate": 0.5}
    assert r["deployers"]["DEV2"]["rug_rate"] == 1.0
    assert r["by_token"]["B"] == 0.5         # inherits DEV1's track record


def test_no_admin_no_entry():
    snaps = {"2026-06-01": {"tokens": {"X": {"price": 1.0}}}}   # no admin recorded
    assert X.token_outcomes(snaps, set()) == {}


if __name__ == "__main__":
    for n, fn in sorted(globals().items()):
        if n.startswith("test_"):
            fn(); print("ok", n)
    print("ALL PASS")
