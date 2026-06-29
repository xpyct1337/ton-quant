#!/usr/bin/env python3
"""Plain-assert tests for desk_factors (run with python3)."""
import desk_factors as F

SPEC = {"id": "f_voltvl", "expr": {"op": "div", "a": "vol24", "b": "tvl"},
        "direction": "high_is_bad", "threshold": 3.0, "horizon": 7}


def test_eval_expr_basic():
    assert F.eval_expr({"op": "div", "a": "vol24", "b": "tvl"},
                       {"vol24": 30.0, "tvl": 10.0}) == 3.0


def test_eval_expr_div_zero_is_zero():
    assert F.eval_expr({"op": "div", "a": "vol24", "b": "tvl"},
                       {"vol24": 5.0, "tvl": 0.0}) == 0.0


def test_eval_expr_unknown_field_rejected():
    try:
        F.eval_expr("nope", {"vol24": 1})
        assert False, "should have raised"
    except ValueError:
        pass


def test_eval_expr_unknown_op_rejected():
    try:
        F.eval_expr({"op": "pow", "a": 2, "b": 3}, {})
        assert False, "should have raised"
    except ValueError:
        pass


def test_factor_signal_invalid_returns_none():
    assert F.factor_signal({"expr": {"op": "div", "a": "ghost", "b": "tvl"}}, {"tvl": 1}) is None


def test_fires_high_is_bad():
    assert F.fires(SPEC, 4.0) is True       # 4 > threshold 3
    assert F.fires(SPEC, 2.0) is False


def test_apply_active_only_raises_to_med_then_high():
    fields = {"vol24": 40.0, "tvl": 10.0}   # vol_tvl=4 fires
    risk, flags = F.apply_active(fields, active=[SPEC])
    assert risk == "med" and flags == ["f_voltvl"]
    two = [SPEC, {"id": "f2", "expr": {"op": "div", "a": "vol24", "b": "tvl"},
                  "direction": "high_is_bad", "threshold": 1.0}]
    risk2, flags2 = F.apply_active(fields, active=two)
    assert risk2 == "high" and len(flags2) == 2


def test_derived_fields():
    d = F.derived({"buys": 8, "sells": 2, "vol24": 50, "tvl": 25})
    assert abs(d["buy_sell_skew"] - 0.6) < 1e-9 and d["vol_tvl"] == 2.0


if __name__ == "__main__":
    for n, fn in sorted(globals().items()):
        if n.startswith("test_"):
            fn(); print("ok", n)
    print("ALL PASS")
