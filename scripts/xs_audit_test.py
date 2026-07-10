#!/usr/bin/env python3
"""Small regression checks for the forward-record audit."""
from xs_audit import build_audit


def test_legacy_rows_are_not_invented():
    audit = build_audit({"records": [{"net": -.1, "close_ts": 10}]}, {"bar_ts": 12})
    assert audit["records"] == {"total": 1, "with_leg_decomposition": 0, "legacy_net_only": 1}
    assert audit["legs"]["available"] is False and audit["as_of_ts"] == 12


def test_new_rows_keep_components():
    row = {"net": .03, "close_ts": 10, "long_gross": .05, "short_gross": .018, "fees": .002}
    audit = build_audit({"records": [row]}, {})
    assert audit["records"]["with_leg_decomposition"] == 1
    assert audit["legs"]["mean_fees"] == .002


if __name__ == "__main__":
    test_legacy_rows_are_not_invented()
    test_new_rows_keep_components()
    print("xs_audit tests: ok")
