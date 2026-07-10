#!/usr/bin/env python3
"""Write a transparent, compact audit of the XS paper forward track record."""
import json
from datetime import datetime, timezone
from pathlib import Path


DATA = Path("data")
EQUITY = DATA / "xs_forward_equity.json"
STATE = DATA / "xs_forward_state.json"
OUTPUT = DATA / "xs_audit.json"


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def build_audit(equity, state):
    records = equity.get("records", []) if isinstance(equity, dict) else []
    records = [row for row in records if isinstance(row, dict) and isinstance(row.get("net"), (int, float))]
    diagnostic = [row for row in records if all(isinstance(row.get(key), (int, float))
                  for key in ("long_gross", "short_gross", "fees"))]
    cumulative = 1.0
    for row in records:
        cumulative *= 1 + row["net"]
    as_of = max([row.get("close_ts", 0) for row in records] + [state.get("bar_ts", 0) if isinstance(state, dict) else 0])
    return {
        "schema": 1,
        "as_of_ts": as_of or None,
        "records": {
            "total": len(records),
            "with_leg_decomposition": len(diagnostic),
            "legacy_net_only": len(records) - len(diagnostic),
        },
        "performance": {
            "cumulative_net": cumulative - 1 if records else 0,
            "mean_net_per_hold": sum(row["net"] for row in records) / len(records) if records else None,
        },
        "legs": {
            "available": bool(diagnostic),
            "mean_long_gross": sum(row["long_gross"] for row in diagnostic) / len(diagnostic) if diagnostic else None,
            "mean_short_gross": sum(row["short_gross"] for row in diagnostic) / len(diagnostic) if diagnostic else None,
            "mean_fees": sum(row["fees"] for row in diagnostic) / len(diagnostic) if diagnostic else None,
        },
        "status": "insufficient_forward_sample" if len(records) < 30 else "forward_sample_building",
        "notes": [
            "Historical net-only rows cannot be decomposed after the fact.",
            "New rows retain long, short and fee components; incomplete baskets are not silently scored.",
            "This is paper tracking, not a trading recommendation.",
        ],
    }


def main():
    audit = build_audit(load(EQUITY, {}), load(STATE, {}))
    audit["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)
    if load(OUTPUT, None) != audit:
        raise RuntimeError("xs audit read-back failed")
    print(f"xs audit: {audit['records']['total']} holds, {audit['records']['with_leg_decomposition']} with leg decomposition")


if __name__ == "__main__":
    main()
