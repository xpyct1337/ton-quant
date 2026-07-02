#!/usr/bin/env python3
"""Plain-assert tests for desk_worker pure helpers (no daemon, no LLM)."""
import json, os, tempfile
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


def test_pick_task_priority_order():
    assert W.pick_task(False, True, 5) == "daily_verdicts"
    assert W.pick_task(True, True, 5) == "calibrate"
    assert W.pick_task(True, False, 5, revalidate_due=True) == "revalidate"
    assert W.pick_task(True, False, 5) == "deep_vetting"
    assert W.pick_task(True, False, 0) == "research"   # idle-filler, never None


def test_data_date_uses_wallets_json_not_system_clock():
    # regression: stale cloud data must not make today_done permanently False
    # (observed live: 59 full daily_verdicts reruns in one day when cloud lagged)
    orig = os.getcwd()
    tmp = tempfile.mkdtemp()
    try:
        os.chdir(tmp)
        os.makedirs("data", exist_ok=True)
        json.dump({"date": "2020-01-01"}, open("data/wallets.json", "w"))
        assert W.data_date() == "2020-01-01"          # NOT today()'s real date
    finally:
        os.chdir(orig)
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


def test_data_date_falls_back_to_today_if_unreadable():
    orig = os.getcwd()
    tmp = tempfile.mkdtemp()
    try:
        os.chdir(tmp)          # no data/wallets.json here
        assert W.data_date() == W.today()
    finally:
        os.chdir(orig)
        import shutil; shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
    print("ALL PASS")
