# Exit Redesign + Aggressive Frequency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the paper bots' exit logic with a layered ladder (break-even stop, trailing stop, smart time-stop) so winners exit in profit or at worst break-even, and push trade frequency aggressively via config (more slots, full universe, lower entry gate) with a per-signal-type cap for diversification.

**Architecture:** Extract a single pure function `decide_exit` holding the whole exit ladder so it is unit-testable in isolation (the repo's established testing style — see `scripts/score_test.py`). Wire it into `run_bot`, which gains one new per-position field `peak` and computes `d1` alongside the existing `dtvl`. Entry loop gains a per-signal-type open cap. Frequency is pure config in `BOTS`, the module constant `MIN_EFF_W`, and `TRACKED` in `universe.py`.

**Tech Stack:** Python 3.12, stdlib only (no deps — conytail). Tests are stdlib self-test scripts run with `python scripts/<name>_test.py`, exit 1 on failure.

---

## File Structure

- `scripts/paper.py` — MODIFY. Add pure `decide_exit`; rewrite the exit block in `run_bot` to call it + track `peak` + compute `d1`; add per-signal cap in the entry loop; update `BOTS` config and `MIN_EFF_W`.
- `scripts/paper_test.py` — CREATE. Stdlib self-tests for `decide_exit` (pure ladder logic).
- `scripts/universe.py` — MODIFY. `TRACKED` 100 → 200.

No new files beyond the test. Daily cadence, snapshot pipeline, and `score.py` are untouched.

---

### Task 1: Pure `decide_exit` exit ladder

**Files:**
- Modify: `scripts/paper.py` (add new top-level function, after `pct`, before `detect_signals`)
- Test: `scripts/paper_test.py` (create)

- [ ] **Step 1: Write the failing test**

Create `scripts/paper_test.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python scripts/paper_test.py`
Expected: FAIL — `ImportError: cannot import name 'decide_exit' from 'paper'`.

- [ ] **Step 3: Write minimal implementation**

In `scripts/paper.py`, add this function immediately after `pct` (the `def pct(...)` block) and before `def detect_signals`:

```python
def decide_exit(cfg, entry_eff, cur, peak, days, dtvl, d1, size_zero):
    """Pure exit decision -> reason string or None. Caller updates `peak`
    (max price since entry) before calling. dtvl/d1 are percent day-over-day
    deltas (pct() output). Ladder order matters: trail and break-even protect
    a position that has run up before the raw stop-loss can fire."""
    ret = cur / entry_eff - 1
    peak_ret = peak / entry_eff - 1
    if dtvl is not None and dtvl < -25:
        return "rug_exit"
    if peak_ret >= cfg["trail_arm"] and ret <= peak_ret - cfg["trail_gap"]:
        return "trail"
    if peak_ret >= cfg["be_arm"] and ret <= cfg["be_floor"]:
        return "breakeven"
    if size_zero and ret <= 0:
        return "edge_fade"
    if ret <= cfg["sl"]:
        return "sl"
    if ret >= cfg["tp"]:
        return "tp"
    if days >= cfg["max_days"]:
        if ret > 0:
            return "time"
        if days < 2 * cfg["max_days"] and (
            (d1 is not None and d1 > 0) or (dtvl is not None and dtvl > 0)):
            return None
        return "time"
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python scripts/paper_test.py`
Expected: `PAPER: 13 passed, 0 failed` (exit 0).

- [ ] **Step 5: Commit**

```bash
git add scripts/paper.py scripts/paper_test.py
git commit -m "feat(paper): pure decide_exit ladder (trail/breakeven/smart-time) + tests"
```

---

### Task 2: Update `BOTS` config and entry gate

**Files:**
- Modify: `scripts/paper.py:10` (`MIN_EFF_W`) and `scripts/paper.py:12-20` (`BOTS`)

- [ ] **Step 1: Lower the entry gate**

Replace line 10:

```python
MIN_EFF_W = 1.0  # skip entries if noise-adjusted priority drops below this
```

with:

```python
MIN_EFF_W = 0.5  # admit more candidates; safe because exits now protect downside
```

- [ ] **Step 2: Replace the `BOTS` dict**

Replace the whole `BOTS = { ... }` block (lines 12-20) with:

```python
BOTS = {
    "cons": {"pos": 100.0, "max_open": 6, "tp": 0.25, "sl": -0.07, "max_days": 5,
             "be_arm": 0.05, "be_floor": 0.005, "trail_arm": 0.10, "trail_gap": 0.05,
             "sig_cap": 2,
             "min_tvl": 50000, "min_holders": 5000, "min_liq_ratio": 0.02,
             "signals": ["hidden_buyer", "holders_surge", "accum_div", "liq_inflow"]},
    "aggr": {"pos": 90.0, "max_open": 12, "tp": 0.50, "sl": -0.12, "max_days": 3,
             "be_arm": 0.08, "be_floor": 0.01, "trail_arm": 0.15, "trail_gap": 0.10,
             "sig_cap": 3,
             "min_tvl": 20000, "min_holders": 500, "min_liq_ratio": 0.0,
             "signals": ["hidden_buyer", "holders_surge", "accum_div", "liq_inflow",
                          "momentum", "breakout", "dip_reversal", "flow_imbalance"]},
}
```

- [ ] **Step 3: Verify the module still imports**

Run: `python -c "import sys; sys.path.insert(0,'scripts'); import paper; print(paper.BOTS['aggr']['max_open'], paper.MIN_EFF_W)"`
Expected: `12 0.5`

- [ ] **Step 4: Re-run exit tests (config keys unchanged for test CFG)**

Run: `python scripts/paper_test.py`
Expected: `PAPER: 13 passed, 0 failed`

- [ ] **Step 5: Commit**

```bash
git add scripts/paper.py
git commit -m "feat(paper): aggressive frequency config + exit params (be/trail/sig_cap)"
```

---

### Task 3: Wire `decide_exit` + `peak` + `d1` into `run_bot`

**Files:**
- Modify: `scripts/paper.py` — the exit loop at the top of `run_bot` (currently lines 126-156)

- [ ] **Step 1: Replace the exit loop**

Replace this current block:

```python
def run_bot(name, cfg, bot, toks, sig_map, prev_map, today, score_mults=None):
    still = []
    for p in bot["positions"]:
        t = toks.get(p["addr"])
        cur = (t or {}).get("price")
        p["days"] += 1
        if not cur:
            still.append(p); continue
        tvl = (t or {}).get("tvl", 0) or 0
        dtvl = pct(tvl, (prev_map.get(p["addr"]) or {}).get("tvl"))
        ret = cur / p["entry_eff"] - 1
        reason = None
        if dtvl is not None and dtvl < -25: reason = "rug_exit"
        elif ret >= cfg["tp"]: reason = "tp"
        # edge-weighted exit: cut early if the entry signal's measured edge has
        # collapsed to zero size (noise verdict or non-positive excess) — the same
        # gate that blocks entry now also closes a stale position. Banks a TP first.
        elif score_mults and score_mults.get(p["signal"], (1.0, 1.0))[1] == 0.0: reason = "edge_fade"
        elif ret <= cfg["sl"]: reason = "sl"
        elif p["days"] >= cfg["max_days"]: reason = "time"
        if reason:
```

with:

```python
def run_bot(name, cfg, bot, toks, sig_map, prev_map, today, score_mults=None):
    still = []
    for p in bot["positions"]:
        t = toks.get(p["addr"])
        cur = (t or {}).get("price")
        p["days"] += 1
        if not cur:
            still.append(p); continue
        prevt = prev_map.get(p["addr"]) or {}
        tvl = (t or {}).get("tvl", 0) or 0
        dtvl = pct(tvl, prevt.get("tvl"))
        d1 = pct(cur, prevt.get("price"))
        p["peak"] = max(p.get("peak", p["entry_eff"]), cur)  # legacy positions: default to entry
        ret = cur / p["entry_eff"] - 1
        size_zero = bool(score_mults) and score_mults.get(p["signal"], (1.0, 1.0))[1] == 0.0
        reason = decide_exit(cfg, p["entry_eff"], cur, p["peak"], p["days"], dtvl, d1, size_zero)
        if reason:
```

Leave everything after `if reason:` (the proceeds/`bot["trades"].append`/`else: still.append(p)` block, current lines 146-156) exactly as-is — it already uses `cur`, `tvl`, `ret`, and `reason`.

- [ ] **Step 2: Verify import + a dry parse**

Run: `python -c "import sys; sys.path.insert(0,'scripts'); import paper; print('ok')"`
Expected: `ok` (no SyntaxError, no NameError).

- [ ] **Step 3: Re-run exit unit tests**

Run: `python scripts/paper_test.py`
Expected: `PAPER: 13 passed, 0 failed`

- [ ] **Step 4: Commit**

```bash
git add scripts/paper.py
git commit -m "feat(paper): run_bot uses decide_exit, tracks peak, computes d1"
```

---

### Task 4: Per-signal-type open cap in the entry loop

**Files:**
- Modify: `scripts/paper.py` — the candidate/entry loop in `run_bot` (currently lines 157-184)

- [ ] **Step 1: Seed signal counts before the candidate loop**

Replace this current line:

```python
    bot["positions"] = still
    open_addrs = {p["addr"] for p in bot["positions"]}
```

with:

```python
    bot["positions"] = still
    open_addrs = {p["addr"] for p in bot["positions"]}
    sig_counts = {}
    for op in bot["positions"]:
        sig_counts[op["signal"]] = sig_counts.get(op["signal"], 0) + 1
```

- [ ] **Step 2: Enforce the cap and record `peak` on entry**

Replace this current block:

```python
    for eff_w, addr, t, sig in cands:
        if len(bot["positions"]) >= cfg["max_open"]: break
        if eff_w < MIN_EFF_W: break  # sorted desc — rest also below threshold
        if addr in open_addrs: continue
        size_mult = (score_mults or {}).get(sig, (1.0, 1.0))[1]
        size = round(position_size(cfg, t) * size_mult, 2)
        if size < MIN_POS or bot["cash"] < size: continue
        tvl = t.get("tvl", 0) or 0
        entry_eff = t["price"] * (1 + min(impact(tvl, size), 0.5) + FEE)
        qty = size / entry_eff
        bot["cash"] -= size
        bot["positions"].append({"addr": addr, "sym": t["sym"], "signal": sig, "opened": today,
                                  "entry_eff": entry_eff, "qty": qty, "size": size, "days": 0})
        open_addrs.add(addr)
```

with:

```python
    for eff_w, addr, t, sig in cands:
        if len(bot["positions"]) >= cfg["max_open"]: break
        if eff_w < MIN_EFF_W: break  # sorted desc — rest also below threshold
        if addr in open_addrs: continue
        if sig_counts.get(sig, 0) >= cfg["sig_cap"]: continue  # diversify: cap per signal type
        size_mult = (score_mults or {}).get(sig, (1.0, 1.0))[1]
        size = round(position_size(cfg, t) * size_mult, 2)
        if size < MIN_POS or bot["cash"] < size: continue
        tvl = t.get("tvl", 0) or 0
        entry_eff = t["price"] * (1 + min(impact(tvl, size), 0.5) + FEE)
        qty = size / entry_eff
        bot["cash"] -= size
        bot["positions"].append({"addr": addr, "sym": t["sym"], "signal": sig, "opened": today,
                                  "entry_eff": entry_eff, "qty": qty, "size": size, "days": 0,
                                  "peak": entry_eff})
        open_addrs.add(addr)
        sig_counts[sig] = sig_counts.get(sig, 0) + 1
```

- [ ] **Step 2b: Verify import**

Run: `python -c "import sys; sys.path.insert(0,'scripts'); import paper; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add scripts/paper.py
git commit -m "feat(paper): per-signal-type open cap + peak field on new positions"
```

---

### Task 5: Widen the tracked universe

**Files:**
- Modify: `scripts/universe.py:9` (the `PAGES, MINVOL, MINLIQ, UNIVERSE, TRACKED = ...` line)

- [ ] **Step 1: Bump TRACKED to 200**

Replace:

```python
PAGES, MINVOL, MINLIQ, UNIVERSE, TRACKED = 10, 5000, 3000, 200, 100
```

with:

```python
PAGES, MINVOL, MINLIQ, UNIVERSE, TRACKED = 10, 5000, 3000, 200, 200
```

- [ ] **Step 2: Verify import**

Run: `python -c "import sys; sys.path.insert(0,'scripts'); import universe; print(universe.TRACKED)"`
Expected: `200`

- [ ] **Step 3: Commit**

```bash
git add scripts/universe.py
git commit -m "feat(universe): track full 200-token universe (was 100)"
```

---

### Task 6: Replay verification on real snapshots

This is an integration check against existing data — no new asserts, an eyeball/diff of paper-bot behavior before vs after. `paper.py` mutates `data/paper/bots.json`, so snapshot it first and restore after.

**Files:**
- Read/run only: `scripts/paper.py`, `data/snapshots/*`, `data/paper/bots.json`

- [ ] **Step 1: Back up live bot state**

Run: `cp data/paper/bots.json /tmp/bots_before.json`
Expected: no output (file copied).

- [ ] **Step 2: Run the bots against the latest snapshot**

Run: `python scripts/paper.py`
Expected: a `paper2: <date> ... equity: {...} score_mults: {...}` line, no traceback.

- [ ] **Step 3: Inspect new exit reasons and trade count**

Run:
```bash
python - <<'PY'
import json
b = json.load(open("data/paper/bots.json"))
for name, bot in b["bots"].items():
    reasons = {}
    for tr in bot["trades"]:
        reasons[tr["reason"]] = reasons.get(tr["reason"], 0) + 1
    greens_gone_red = sum(1 for tr in bot["trades"] if tr["ret"] < 0 and tr["reason"] in ("time","sl"))
    print(name, "trades=", len(bot["trades"]), "open=", len(bot["positions"]),
          "reasons=", reasons, "red_time_or_sl=", greens_gone_red)
PY
```
Expected: `reasons` now includes `trail` and/or `breakeven` buckets once positions mature; `open` can exceed the old caps (up to 6/12, cash permitting). On the first run after deploy, existing positions lack `peak` and arm one snapshot later — that is expected.

- [ ] **Step 4: Restore live state if this was only a dry check**

Run: `cp /tmp/bots_before.json data/paper/bots.json`
Expected: no output. (Skip this step if you intend the run to be the real daily update; in CI the daily workflow runs `paper.py` itself.)

- [ ] **Step 5: Final commit (docs only — code already committed per task)**

```bash
git add docs/superpowers/plans/2026-06-24-exit-frequency-redesign.md
git commit -m "docs: exit/frequency implementation plan"
```

---

## Notes for the implementer

- **Do not push.** Igor's machine holds the SSH key; commit locally and he runs `deploy.bat`. The `data/**` and `scripts/**` paths are ignored by the deploy workflow, so these code changes ship via the daily snapshot workflow / manual deploy, not Pages rebuild.
- **Mount write caveat:** the working tree is OneDrive-synced and has truncated large writes before. After each `Edit`/`Write` to `paper.py`, confirm the change is intact (`python -c "import ...; print('ok')"` already does this) before committing.
- **Stdlib only.** No `pip install`. Tests are plain scripts, not pytest.
- **`d1`/`dtvl` units:** `pct()` returns percentages (×100), so `dtvl < -25` means −25%, and `cfg` fractions (`tp=0.25`) compare against `ret` which is a fraction — keep them on the right sides.

## Self-Review

- **Spec coverage:** exit ladder steps 1-7 → Task 1 `decide_exit` + Task 3 wiring; per-bot params table → Task 2; `peak` field + legacy default → Task 3 (`p.get("peak", ...)`) and Task 4 (new positions); diversification per-signal cap → Task 4; frequency (max_open/pos/MIN_EFF_W) → Task 2, TRACKED → Task 5; new `reason` values surface in journals automatically; testing/replay → Task 1 unit tests + Task 6 replay. All spec sections mapped.
- **Placeholder scan:** none — every code step shows full code; commands have expected output.
- **Type/name consistency:** `decide_exit(cfg, entry_eff, cur, peak, days, dtvl, d1, size_zero)` signature is identical in Task 1 definition, Task 1 tests, and Task 3 call site. `peak`, `sig_cap`, `be_arm`, `be_floor`, `trail_arm`, `trail_gap` names match across config (Task 2), function (Task 1), and call sites (Tasks 3-4).
