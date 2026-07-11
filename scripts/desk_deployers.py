#!/usr/bin/env python3
"""Deployer registry: repeat-offender scoring from accumulated snapshot history.

snapshot.py records each token's `admin` (deployer) daily since 01.07.2026. This
module aggregates: deployer -> tokens launched -> how many "rugged" (wash-banned by
the detector, or price collapsed to <20% of its observed peak). A new token from a
wallet whose previous tokens rugged is high-risk BEFORE any market signal exists —
the literature's strongest cheap rug predictor.

Output data/desk/deployers.json:
  {"deployers": {admin: {tokens, rugged, rug_rate}}, "by_token": {addr: dep_rug}}

dep_rug feeds agent-1's LIVE evidence only — NOT the researcher's historical gate
(a full-history score applied to past dates would be lookahead bias).

Run from repo root (worker calibrate cadence). Self-test: desk_deployers_test.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_features import load, load_snaps  # noqa: E402

COLLAPSE = 0.2   # last price below 20% of observed peak = collapsed
ZERO_ADMIN = "0:" + "0" * 64


def token_outcomes(snaps, wash_ban):
    """{token_addr: {"admin": last-known admin, "rugged": bool}} from history."""
    px, admin = {}, {}
    for d in sorted(snaps):
        for a, t in (snaps[d].get("tokens", {}) or {}).items():
            if t.get("price"):
                px.setdefault(a, []).append(t["price"])
            if t.get("admin"):
                admin[a] = t["admin"]
    out = {}
    for a, dep in admin.items():
        p = px.get(a, [])
        collapsed = len(p) >= 5 and p[-1] < COLLAPSE * max(p)
        out[a] = {"admin": dep, "rugged": (a in wash_ban) or collapsed}
    return out


def build_registry(outcomes):
    deps = {}
    for a, o in outcomes.items():
        e = deps.setdefault(o["admin"], {"tokens": 0, "rugged": 0})
        e["tokens"] += 1
        e["rugged"] += 1 if o["rugged"] else 0
    for e in deps.values():
        e["rug_rate"] = round(e["rugged"] / e["tokens"], 3)
    by_token = {a: deps[o["admin"]]["rug_rate"] for a, o in outcomes.items()}
    return {"deployers": deps, "by_token": by_token}


def _first_admins(snaps):
    """Return the first observed deployer and first-seen date for each token."""
    admins, dates = {}, {}
    for date in sorted(snaps):
        for addr, token in (snaps[date].get("tokens", {}) or {}).items():
            admin = token.get("admin")
            if admin and admin != ZERO_ADMIN:
                admins.setdefault(addr, admin)
                dates.setdefault(addr, date)
    return admins, dates


def point_in_time_records(snaps):
    """Score new tokens only from earlier observed outcomes of the same deployer.

    This is a diagnostic, not a live factor: final outcomes are used only as the
    evaluation label. ``wash_ban`` is intentionally excluded to avoid importing a
    future detector decision into an earlier score.
    """
    admins, first_seen = _first_admins(snaps)
    final = token_outcomes(snaps, set())
    records = []
    for addr, date in sorted(first_seen.items(), key=lambda item: (item[1], item[0])):
        admin = admins[addr]
        prior = [other for other, other_date in first_seen.items()
                 if other_date < date and admins.get(other) == admin]
        if not prior or addr not in final:
            continue
        visible = {day: snaps[day] for day in sorted(snaps) if day <= date}
        outcomes = token_outcomes(visible, set())
        labels = [outcomes[other]["rugged"] for other in prior if other in outcomes]
        if not labels:
            continue
        records.append({
            "addr": addr,
            "date": date,
            "admin": admin,
            "prior_tokens": len(labels),
            "prior_rug_rate": round(sum(labels) / len(labels), 3),
            "rugged": bool(final[addr]["rugged"]),
        })
    return records


def point_in_time_report(snaps):
    """Compare high/low prior-rug buckets; fail closed on a thin sample."""
    records = point_in_time_records(snaps)
    high = [r for r in records if r["prior_rug_rate"] >= 0.5]
    low = [r for r in records if r["prior_rug_rate"] < 0.5]
    admin_days = [day for day in sorted(snaps) if any(
        token.get("admin") and token.get("admin") != ZERO_ADMIN
        for token in (snaps[day].get("tokens", {}) or {}).values()
    )]

    def bucket(rows):
        return {
            "n": len(rows),
            "rugs": sum(row["rugged"] for row in rows),
            "rug_rate": round(sum(row["rugged"] for row in rows) / len(rows), 3) if rows else None,
        }

    # ponytail: one fixed 5-token floor keeps the diagnostic descriptive; replace
    # with a confidence-bounded test after the point-in-time panel grows.
    missing = []
    if len(records) < 5:
        missing.append("records>=5")
    if not high:
        missing.append("high_bucket")
    if not low:
        missing.append("low_bucket")
    return {
        "schema": 1,
        "available": not missing,
        "missing": missing,
        "admin_coverage": {
            "days": len(admin_days),
            "first_date": admin_days[0] if admin_days else None,
            "last_date": admin_days[-1] if admin_days else None,
        },
        "records": len(records),
        "high_prior_rug": bucket(high),
        "low_prior_rug": bucket(low),
    }


def main():
    snaps = load_snaps()
    wash_ban = set((load("data/paper/bots.json", {}) or {}).get("wash_ban", {}).keys())
    reg = build_registry(token_outcomes(snaps, wash_ban))
    os.makedirs("data/desk", exist_ok=True)
    with open("data/desk/deployers.json", "w") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
    n = len(reg["deployers"])
    hot = sum(1 for e in reg["deployers"].values() if e["rug_rate"] > 0)
    print(f"deployers: {n} known ({hot} with rugs), {len(reg['by_token'])} tokens scored", flush=True)
    report = point_in_time_report(snaps)
    print("deployer point-in-time:", json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
