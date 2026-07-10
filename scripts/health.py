#!/usr/bin/env python3
"""Build and validate the small data-health contract used by /brief.

The collectors remain file-only: this script only inspects their latest committed
outputs.  Optional collector failures are passed by the daily workflow and remain
visible until that collector succeeds on a later daily run.
"""
import argparse
import datetime as dt
import json
from pathlib import Path


DATA = Path("data")
HEALTH = DATA / "health.json"

# source -> (maximum age in hours, extractor).  `updated_at` is normalized to ISO
# so the browser can re-check staleness between daily health writes.
SPECS = {
    "snapshot": (30, lambda d: _snapshot(d)),
    "intraday": (6, lambda d: _intraday(d)),
    "wallets": (30, lambda d: _dated(d / "wallets.json", "roster")),
    "flows": (30, lambda d: _dated(d / "flows.json", "tokens")),
    "social": (30, lambda d: _dated(d / "social.json", "tokens")),
    "forensics": (30, lambda d: _dated(d / "forensics.json", "tokens")),
    "signals": (30, lambda d: _dated(d / "signals" / "scores.json", "per_sig", "updated")),
    "xs_forward": (54, lambda d: _xs_forward(d)),
    "xs_audit": (54, lambda d: _xs_audit(d)),
    "perp_markets": (3, lambda d: _dated(d / "perp_markets.json", "ctxs", "updated")),
    "perp_signals": (6, lambda d: _dated(d / "perp_signals.json", "signals", "updated")),
    "dex_signals": (6, lambda d: _dated(d / "dex_signals.json", "signals", "updated")),
    "desk": (36, lambda d: _dated(d / "desk" / "verdicts.json", "wallets", "date")),
}


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _as_time(value):
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return dt.datetime.fromtimestamp(seconds, dt.timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        if len(value) == 10:
            # Daily files are produced around 03:10 UTC; anchoring prevents a
            # fresh same-day snapshot from looking 24 hours old in the browser.
            return dt.datetime.fromisoformat(value + "T03:10:00+00:00")
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        return None


def _dated(path, count_key, updated_key="date"):
    item = load(path)
    if not isinstance(item, dict):
        raise FileNotFoundError(path)
    updated = item.get(updated_key)
    when = _as_time(updated)
    if when is None:
        raise ValueError(f"no timestamp in {path}")
    values = item.get(count_key, {})
    return updated, when, len(values) if hasattr(values, "__len__") else 0


def _snapshot(data):
    idx = load(data / "index.json")
    if not isinstance(idx, dict) or not idx.get("dates"):
        raise FileNotFoundError(data / "index.json")
    updated = idx["dates"][-1]
    snap = load(data / "snapshots" / f"{updated}.json", {})
    when = _as_time(updated)
    return updated, when, len(snap.get("tokens", {}))


def _intraday(data):
    files = sorted((data / "intraday").glob("*.json"))
    if not files:
        raise FileNotFoundError(data / "intraday")
    item = load(files[-1])
    updated = item.get("date") or files[-1].stem
    when = _as_time(item.get("ts")) or _as_time(updated)
    if when is None:
        raise ValueError(f"no timestamp in {files[-1]}")
    return updated, when, len(item.get("tokens", {}))


def _xs_forward(data):
    state = load(data / "xs_forward_state.json")
    if not isinstance(state, dict):
        raise FileNotFoundError(data / "xs_forward_state.json")
    updated = state.get("bar_ts")
    when = _as_time(updated)
    if when is None:
        raise ValueError("no bar_ts in xs_forward_state.json")
    return updated, when, len(state.get("long", [])) + len(state.get("short", []))


def _xs_audit(data):
    item = load(data / "xs_audit.json")
    if not isinstance(item, dict):
        raise FileNotFoundError(data / "xs_audit.json")
    updated = item.get("as_of_ts")
    when = _as_time(updated)
    if when is None:
        raise ValueError("no as_of_ts in xs_audit.json")
    return updated, when, item.get("records", {}).get("total", 0)


def json_errors(data_dir=DATA):
    bad = []
    for path in data_dir.rglob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                json.load(f)
        except (OSError, json.JSONDecodeError):
            bad.append(str(path))
    return bad


def build_health(data_dir=DATA, now=None, checked=(), failed=(), previous=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    checked, failed = set(checked), set(failed)
    previous = previous if isinstance(previous, dict) else {}
    old_sources = previous.get("sources", {}) if isinstance(previous.get("sources", {}), dict) else {}
    sources = {}

    for name, (max_age_h, extractor) in SPECS.items():
        old = old_sources.get(name, {})
        try:
            updated, when, count = extractor(data_dir)
            age_h = round(max(0.0, (now - when).total_seconds() / 3600), 1)
            status = "ok" if age_h <= max_age_h else "stale"
            error = None
        except (FileNotFoundError, ValueError, TypeError):
            updated, when, count, age_h, status = None, None, 0, None, "missing"
            error = "output missing or unreadable"

        if name in failed:
            status, error = "error", "collector failed in the latest daily run"
        elif name not in checked and old.get("status") == "error":
            status, error = "error", old.get("last_error")

        sources[name] = {
            "status": status,
            "updated": updated,
            "updated_at": when.isoformat().replace("+00:00", "Z") if when else None,
            "age_h": age_h,
            "max_age_h": max_age_h,
            "count": count,
            "last_error": error,
        }

    return {"generated_at": now.isoformat().replace("+00:00", "Z"), "sources": sources}


def write_health(health, path=HEALTH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(health, f, ensure_ascii=False, indent=2)
    if load(path) != health:
        raise RuntimeError("health read-back failed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--checked", nargs="*", default=[])
    parser.add_argument("--failed", nargs="*", default=[])
    args = parser.parse_args()

    bad = json_errors()
    if args.validate and bad:
        raise SystemExit("invalid JSON: " + ", ".join(bad))

    previous = load(HEALTH, {})
    health = build_health(checked=args.checked, failed=[x for x in args.failed if x], previous=previous)
    if args.write:
        write_health(health)
    print("health:", ", ".join(f"{name}={row['status']}" for name, row in health["sources"].items()))


if __name__ == "__main__":
    main()
