#!/usr/bin/env python3
"""Self-tests for score.py statistics (Wilson lo, sign test, verdict).
Pure stdlib, no repo data needed. Run: python scripts/score_test.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import wilson_lo, sign_test_p, agg_returns, classify

p = f = 0
def t(name, cond, info=""):
    global p, f
    if cond: p += 1
    else: f += 1; print("FAIL:", name, info)

# ---- wilson_lo ----
t("wilson n=0 -> None", wilson_lo(0, 0) is None)
t("wilson 5/10 ~ 23.7%", abs(wilson_lo(5, 10) - 23.7) < 0.5, wilson_lo(5, 10))
t("wilson lo <= point est", wilson_lo(5, 10) < 50)
t("wilson 10/10 high but <100", 60 < wilson_lo(10, 10) < 100, wilson_lo(10, 10))
t("wilson monotonic in wins", wilson_lo(9, 10) > wilson_lo(5, 10))
t("wilson tighter with n", wilson_lo(80, 100) > wilson_lo(8, 10))  # same p=0.8

# ---- sign_test_p ----
t("sign n=0 -> None", sign_test_p(0, 0) is None)
t("sign 5/5 -> 1.0", sign_test_p(5, 5) == 1.0, sign_test_p(5, 5))
t("sign 10/0 significant", sign_test_p(10, 0) < 0.01, sign_test_p(10, 0))
t("sign 8/2 ~ 0.109", abs(sign_test_p(8, 2) - 0.1094) < 0.001, sign_test_p(8, 2))
t("sign symmetric", sign_test_p(8, 2) == sign_test_p(2, 8))

# ---- agg_returns ----
a = agg_returns([2, -1, 3, -4])
t("agg n", a["n"] == 4)
t("agg wr", a["wr"] == 50.0, a["wr"])
t("agg avg", a["avg"] == 0.0, a["avg"])
t("agg empty", agg_returns([])["n"] == 0 and agg_returns([])["wr"] is None)

# ---- classify (verdict logic) ----
t("classify empty -> collecting", classify([])[0] == "collecting")
t("classify <min_n -> collecting", classify([1, 2])[0] == "collecting")
t("classify 3/3 wins still neutral (n too small for sig)", classify([1, 2, 3])[0] == "neutral",
  classify([1, 2, 3]))
t("classify 8/8 wins -> edge", classify([1.0] * 8)[0] == "edge", classify([1.0] * 8))
t("classify neg avg -> noise", classify([-1, -2, -3])[0] == "noise")
t("classify low wr -> noise", classify([1, -1, -2, 3, -4])[0] == "noise",
  classify([1, -1, -2, 3, -4]))
t("classify edge needs wilson>50", classify([1.0] * 8)[1] > 50)

print("\nSCORE: %d passed, %d failed" % (p, f))
sys.exit(1 if f else 0)
