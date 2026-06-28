#!/usr/bin/env python3
"""Plain-assert tests for desk_worker pure helpers (no daemon, no LLM)."""
import desk_worker as W


def test_thermal_decision_on_battery_sleeps():
    d = W.thermal_decision(on_ac=False, speed_limit=100)
    assert d["run"] is False and d["sleep"] >= 240


def test_thermal_decision_throttled_backs_off():
    d = W.thermal_decision(on_ac=True, speed_limit=60)
    assert d["run"] is True and d["sleep"] >= 60   # works but cools longer


def test_thermal_decision_normal_runs():
    d = W.thermal_decision(on_ac=True, speed_limit=100)
    assert d["run"] is True and d["sleep"] <= 60


def test_pick_task_prioritizes_daily_then_calibrate_then_deep():
    assert W.pick_task(today_done=False, calib_stale=True, deep_pending=5) == "daily_verdicts"
    assert W.pick_task(today_done=True, calib_stale=True, deep_pending=5) == "calibrate"
    assert W.pick_task(today_done=True, calib_stale=False, deep_pending=5) == "deep_vetting"
    assert W.pick_task(today_done=True, calib_stale=False, deep_pending=0) is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
    print("ALL PASS")
