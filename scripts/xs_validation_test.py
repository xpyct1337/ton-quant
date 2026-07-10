#!/usr/bin/env python3
"""Runnable checks for leakage-safe XS diagnostics."""
from xs_validation import basket_outcome, cscv_pbo, sharpe_diagnostic


def test_cscv_rank_is_relative_to_alternatives():
    timestamps = list(range(16))
    report = cscv_pbo({
        "steady": {ts: 0.02 for ts in timestamps},
        "weak": {ts: -0.01 for ts in timestamps},
    }, groups=4, embargo_ms=0)
    assert report["splits"] == 6
    assert report["pbo"] == 0
    assert report["median_test_rank"] == 0.75


def test_embargo_removes_neighbours():
    timestamps = list(range(16))
    report = cscv_pbo({"a": {ts: ts for ts in timestamps}, "b": {ts: -ts for ts in timestamps}}, groups=4, embargo_ms=1)
    assert report["median_train_observations"] < 8


def test_basket_never_drops_missing_leg():
    pos = {"long": ["L"], "short": ["S"], "entry": {"L": 10, "S": 10}}
    assert basket_outcome(pos, {"L": 11}, 0.001)["complete"] is False
    outcome = basket_outcome(pos, {"L": 11, "S": 9}, 0.001)
    assert outcome["complete"] and round(outcome["net"], 5) == 0.198


def test_sharpe_diagnostic_is_bounded():
    report = sharpe_diagnostic([.01, .02, -.01, .03], trial_count=3)
    assert report["available"] and 0 <= report["bonferroni_adjusted_probability"] <= 1


if __name__ == "__main__":
    for name, func in sorted(globals().items()):
        if name.startswith("test_"):
            func()
    print("xs_validation tests: ok")
