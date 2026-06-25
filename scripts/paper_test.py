#!/usr/bin/env python3
"""Self-tests for paper.py exit ladder (decide_exit). Pure stdlib, no repo data.
Run: python scripts/paper_test.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paper import decide_exit

CFG = {"tp": 0.25, "sl": -0.07, "max_days": 5,
       "be_arm": 0.05, "be_floor": 0.005, "trail_arm": 0.10, "trail_gap": 0.05}
E = 1.0  # entry_eff

p = f = 0
def t(name, cond, info=""):
    global p, f
    if cond: p += 1
    else: f += 1; print("FAIL:", name, info)

# hold when flat and young
t("hold flat young", decide_exit(CFG, E, 1.01, 1.01, 1, 0.0, 0.0, False) is None)
# rug always wins
t("rug exit", decide_exit(CFG, E, 1.0, 1.0, 1, -30.0, 0.0, False) == "rug_exit")
# break-even: armed at +6% peak, back to entry -> breakeven
t("breakeven protects winner", decide_exit(CFG, E, 1.0, 1.06, 2, 0.0, 0.0, False) == "breakeven")
# trailing: peak +12%, retrace to +7% (>=gap) -> trail
t("trail captures faded winner", decide_exit(CFG, E, 1.07, 1.12, 2, 0.0, 0.0, False) == "trail")
# sl active before BE arms (peak never reached be_arm)
t("sl before BE arm", decide_exit(CFG, E, 0.92, 1.02, 2, 0.0, -1.0, False) == "sl")
# once armed, BE supersedes sl even on a hard drop
t("BE supersedes sl when armed", decide_exit(CFG, E, 0.90, 1.06, 2, 0.0, 0.0, False) == "breakeven")
# tp cap on a straight run with no retrace
t("tp cap", decide_exit(CFG, E, 1.25, 1.25, 1, 0.0, 5.0, False) == "tp")
# edge_fade only on a non-winner
t("edge_fade loser", decide_exit(CFG, E, 0.99, 1.0, 1, 0.0, 0.0, True) == "edge_fade")
t("edge_fade not winner", decide_exit(CFG, E, 1.20, 1.20, 1, 0.0, 0.0, True) != "edge_fade")
# smart time-stop
t("time exit in profit", decide_exit(CFG, E, 1.03, 1.04, 5, 0.0, 0.0, False) == "time")
t("time hold red trending", decide_exit(CFG, E, 0.96, 1.0, 5, 5.0, 1.0, False) is None)
t("time exit red dead", decide_exit(CFG, E, 0.96, 1.0, 5, -1.0, -1.0, False) == "time")
t("hard time cap at 2x", decide_exit(CFG, E, 0.96, 1.0, 10, 5.0, 5.0, False) == "time")

print("\nPAPER: %d passed, %d failed" % (p, f))
sys.exit(1 if f else 0)
