#!/usr/bin/env python3
"""Plain asserts for scripts/health.py (no network, no repo writes)."""
import datetime as dt
import json
import tempfile
from pathlib import Path

import health as H


NOW = dt.datetime(2026, 7, 10, 4, tzinfo=dt.timezone.utc)


def put(root, rel, value):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def seeded_data(root):
    put(root, "index.json", {"dates": ["2026-07-10"]})
    put(root, "snapshots/2026-07-10.json", {"tokens": {"A": {}}})
    put(root, "intraday/2026-07-10.json", {"date": "2026-07-10", "ts": 1783656000000, "tokens": {"A": {}}})
    put(root, "wallets.json", {"date": "2026-07-10", "wallets": []})
    for name in ("flows", "social", "forensics"):
        put(root, f"{name}.json", {"date": "2026-07-10", "tokens": {"A": {}}})
    put(root, "signals/scores.json", {"updated": "2026-07-10", "per_sig": {"x": {}}})
    put(root, "xs_forward_state.json", {"bar_ts": 1783656000000, "long": ["A"], "short": ["B"]})
    put(root, "xs_audit.json", {"as_of_ts": 1783656000000, "records": {"total": 0}})
    put(root, "perp_markets.json", {"updated": 1783656000000, "ctxs": {"A": {}}})
    for name in ("perp_signals", "dex_signals"):
        put(root, f"{name}.json", {"updated": "2026-07-10T03:00:00Z", "signals": [1]})
    put(root, "desk/verdicts.json", {"date": "2026-07-10", "wallets": []})


def test_health_marks_fresh_files_ok():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        seeded_data(root)
        health = H.build_health(root, now=NOW, checked=H.SPECS)
        assert all(x["status"] == "ok" for x in health["sources"].values())
        assert health["sources"]["snapshot"]["count"] == 1


def test_health_keeps_optional_failure_visible():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        seeded_data(root)
        health = H.build_health(root, now=NOW, checked={"flows"}, failed={"flows"})
        flow = health["sources"]["flows"]
        assert flow["status"] == "error" and "failed" in flow["last_error"]


def test_json_errors_finds_invalid_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "bad.json").write_text("{", encoding="utf-8")
        assert H.json_errors(root) == [str(root / "bad.json")]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
    print("ALL PASS")
