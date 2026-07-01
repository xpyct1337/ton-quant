#!/usr/bin/env python3
"""Plain-assert tests for desk_researcher.gate (no LLM)."""
import desk_researcher as R


def _snaps_with_signal():
    # 20 dates (enough for >=MIN_FIRED in each split); high vol_tvl (BAD) decays,
    # low vol_tvl (GOOD) rises -> the factor predicts BAD underperformance.
    snaps = {}
    for i in range(20):
        d = f"2026-02-{i+1:02d}"
        snaps[d] = {"tokens": {
            "BAD": {"vol24": 90.0, "tvl": 10.0, "price": 100.0 - i * 2},
            "GOOD": {"vol24": 5.0, "tvl": 100.0, "price": 60.0 + i * 2},
        }}
    return snaps


SPEC = {"id": "f_vt", "expr": {"op": "div", "a": "vol24", "b": "tvl"},
        "direction": "high_is_bad", "threshold": 3.0, "horizon": 1}


def test_gate_accepts_planted_signal():
    g = R.gate(SPEC, _snaps_with_signal(), trials=1)
    assert g is not None and g["passed"] is True, g


def test_gate_rejects_noise():
    snaps = {f"2026-03-{i+1:02d}": {"tokens": {"X": {"vol24": 90.0, "tvl": 10.0, "price": 100.0}}}
             for i in range(10)}
    g = R.gate(SPEC, snaps, trials=1)
    assert g is None or g["passed"] is False


def test_deflated_bar_tightens_with_trials():
    g1 = R.gate(SPEC, _snaps_with_signal(), trials=1)
    g100 = R.gate(SPEC, _snaps_with_signal(), trials=100)
    assert g100["bar"] < g1["bar"]   # more trials -> stricter


if __name__ == "__main__":
    for n, fn in sorted(globals().items()):
        if n.startswith("test_"):
            fn(); print("ok", n)
    print("ALL PASS")
