# Agent-Researcher Implementation Plan (Phase 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A 24/7 researcher that has the LLM propose constrained-DSL token factors, tests them under a walk-forward OOS gate (with an anti-overfit deflated bar), and auto-promotes survivors into the desk's risk computation — with a full append-only edit history and hard safety rails (floors stay non-overridable).

**Architecture:** Factors are safe JSON expression trees (no exec) over whitelisted snapshot fields. `desk_factors.py` interprets them + owns the active registry/history/CLI. `desk_researcher.py` proposes (LLM) → gates (reuses `score.py` Wilson/sign-test on forward excess from `desk_calibration.py`) → promotes/demotes. New `research`/`revalidate` task-runners in `desk_worker.py` use spare 24/7 cycles. `desk.py` applies active factors as `max(floor, factor, llm)` so they can only raise risk.

**Tech Stack:** Python 3.11 (stdlib only), Osaurus `:1337` (`qwen3-4b-4bit`), launchd. Tests are plain-assert `scripts/*_test.py` run with `python3` (repo convention).

---

## File Structure

- **Create** `scripts/desk_factors.py` — DSL interpreter (`eval_expr`, `factor_signal`, `fires`), derived fields, active registry (`load_active`/`promote`/`demote`), append-only history, `apply_active`, CLI (`--list`/`--disable`). One responsibility: factor representation + storage.
- **Create** `scripts/desk_factors_test.py` — DSL + registry + safety tests.
- **Create** `scripts/desk_researcher.py` — `propose` (LLM), `gate` (OOS), `research_once`, `revalidate`. One responsibility: discovery + validation.
- **Create** `scripts/desk_researcher_test.py` — gate accepts a planted signal, rejects noise; deflated bar tightens with trials.
- **Modify** `scripts/desk_features.py` — attach raw snapshot `fields` to each token dict (factors need raw fields).
- **Modify** `scripts/desk.py` — apply active factors in token `agent1` (`max(floor, factor, llm)`).
- **Modify** `scripts/desk_worker.py` — add `research`/`revalidate` task-runners + picker priority.

Runtime outputs (committed by the worker, scoped to `data/desk/`): `factors_active.json`, `factors_history.json`.

**Pre-work (do once, before editing worker source):** the live daemon imports these modules at start and won't see edits until reloaded; its 30-min commit cycle could autostash mid-edit. Unload it during the build, reload at the end.

```bash
launchctl unload ~/Library/LaunchAgents/com.tonquant.worker.plist
launchctl list | grep tonquant.worker || echo "worker stopped for build"
```

---

### Task 1: desk_factors.py — DSL, registry, safety

**Files:**
- Create: `scripts/desk_factors.py`
- Test: `scripts/desk_factors_test.py`

- [ ] **Step 1: Write the failing test**

Create `scripts/desk_factors_test.py`:

```python
#!/usr/bin/env python3
"""Plain-assert tests for desk_factors (run with python3)."""
import desk_factors as F

SPEC = {"id": "f_voltvl", "expr": {"op": "div", "a": "vol24", "b": "tvl"},
        "direction": "high_is_bad", "threshold": 3.0, "horizon": 7}

def test_eval_expr_basic():
    assert F.eval_expr({"op": "div", "a": "vol24", "b": "tvl"},
                       {"vol24": 30.0, "tvl": 10.0}) == 3.0

def test_eval_expr_div_zero_is_zero():
    assert F.eval_expr({"op": "div", "a": "vol24", "b": "tvl"},
                       {"vol24": 5.0, "tvl": 0.0}) == 0.0

def test_eval_expr_unknown_field_rejected():
    try:
        F.eval_expr("nope", {"vol24": 1})
        assert False, "should have raised"
    except ValueError:
        pass

def test_eval_expr_unknown_op_rejected():
    try:
        F.eval_expr({"op": "pow", "a": 2, "b": 3}, {})
        assert False, "should have raised"
    except ValueError:
        pass

def test_factor_signal_invalid_returns_none():
    assert F.factor_signal({"expr": {"op": "div", "a": "ghost", "b": "tvl"}}, {"tvl": 1}) is None

def test_fires_high_is_bad():
    assert F.fires(SPEC, 4.0) is True       # 4 > threshold 3
    assert F.fires(SPEC, 2.0) is False

def test_apply_active_only_raises_to_med_then_high():
    fields = {"vol24": 40.0, "tvl": 10.0}   # vol_tvl=4 fires
    risk, flags = F.apply_active(fields, active=[SPEC])
    assert risk == "med" and flags == ["f_voltvl"]
    two = [SPEC, {"id": "f2", "expr": {"op": "div", "a": "vol24", "b": "tvl"},
                  "direction": "high_is_bad", "threshold": 1.0}]
    risk2, flags2 = F.apply_active(fields, active=two)
    assert risk2 == "high" and len(flags2) == 2

def test_derived_fields():
    d = F.derived({"buys": 8, "sells": 2, "vol24": 50, "tvl": 25})
    assert abs(d["buy_sell_skew"] - 0.6) < 1e-9 and d["vol_tvl"] == 2.0

if __name__ == "__main__":
    for n, fn in sorted(globals().items()):
        if n.startswith("test_"):
            fn(); print("ok", n)
    print("ALL PASS")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/ton-quant/scripts && python3 desk_factors_test.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'desk_factors'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/desk_factors.py`:

```python
#!/usr/bin/env python3
"""TON Quant v3.0 — factor DSL + active registry (Phase 2 researcher).

Factors are SAFE JSON expression trees over whitelisted snapshot fields — never
executed code. desk_researcher.py discovers them; desk.py applies the active set.
Active factors can only RAISE a token's risk (max with floor), never lower it.

Active set: data/desk/factors_active.json   (cap MAX_ACTIVE)
Audit log : data/desk/factors_history.json  (append-only)
CLI: python3 scripts/desk_factors.py --list | --disable <id> [--note "..."]
Run from repo root. Self-test: scripts/desk_factors_test.py
"""
import json, os, sys, time

ACTIVE = "data/desk/factors_active.json"
HISTORY = "data/desk/factors_history.json"
MAX_ACTIVE = 8
FIELDS = ("vol24", "tvl", "holders", "buys", "sells", "mcap", "supply", "price", "pools")
DERIVED = ("buy_sell_skew", "vol_tvl")
OPS = ("div", "mul", "sub", "add", "abs", "min", "max", "const")


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def derived(fields):
    b, s = fields.get("buys") or 0, fields.get("sells") or 0
    v, t = fields.get("vol24") or 0, fields.get("tvl") or 0
    d = dict(fields)
    d["buy_sell_skew"] = abs(b - s) / (b + s) if (b + s) > 0 else 0.0
    d["vol_tvl"] = v / t if t > 0 else 0.0
    return d


def eval_expr(expr, fields):
    """Recursively evaluate a whitelisted expression. Raises ValueError on unknown
    field/op (invalid factor). Division by zero -> 0.0. NO eval/exec."""
    if isinstance(expr, (int, float)):
        return float(expr)
    if isinstance(expr, str):
        if expr not in fields and expr not in DERIVED:
            raise ValueError(f"unknown field {expr}")
        return float(fields.get(expr, 0) or 0)
    if not isinstance(expr, dict) or "op" not in expr:
        raise ValueError("bad expr")
    op = expr["op"]
    if op not in OPS:
        raise ValueError(f"unknown op {op}")
    if op == "const":
        return float(expr.get("value", 0))
    a = eval_expr(expr["a"], fields)
    if op == "abs":
        return abs(a)
    b = eval_expr(expr["b"], fields)
    if op == "div":
        return a / b if b != 0 else 0.0
    return {"mul": a * b, "sub": a - b, "add": a + b,
            "min": min(a, b), "max": max(a, b)}[op]


def factor_signal(spec, raw_fields):
    """Scalar signal for a token; None if the factor is invalid for these fields."""
    try:
        return eval_expr(spec["expr"], derived(raw_fields))
    except Exception:
        return None


def fires(spec, signal):
    if signal is None:
        return False
    thr = spec.get("threshold", 0)
    return signal > thr if spec.get("direction") == "high_is_bad" else signal < thr


def apply_active(raw_fields, active=None):
    """-> (risk_level, flags) contributed by active factors. Only raises risk:
    1 fired factor -> 'med', >=2 -> 'high'. Never lowers (caller maxes with floor)."""
    active = active if active is not None else load(ACTIVE, [])
    flags = [s["id"] for s in active if fires(s, factor_signal(s, raw_fields))]
    risk = "high" if len(flags) >= 2 else ("med" if flags else "low")
    return risk, flags


# ---------- registry ----------
def load_active():
    return load(ACTIVE, [])


def _save_active(active):
    os.makedirs("data/desk", exist_ok=True)
    with open(ACTIVE, "w") as f:
        json.dump(active, f, ensure_ascii=False, indent=2)


def history_append(action, factor, metrics=None, reason=""):
    h = load(HISTORY, [])
    h.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": action,
              "factor": factor, "metrics": metrics or {}, "reason": reason})
    os.makedirs("data/desk", exist_ok=True)
    with open(HISTORY, "w") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)


def trials_count():
    return sum(1 for e in load(HISTORY, []) if e["action"] == "proposed")


def promote(spec, metrics, reason="auto"):
    """Add to active if not a dup and there is room (or it beats the weakest)."""
    active = load_active()
    if any(a.get("expr") == spec["expr"] for a in active):
        return False
    rank = lambda a: (a.get("metrics", {}).get("oos", {}).get("wilson_lo") or 0)
    if len(active) >= MAX_ACTIVE:
        weakest = min(active, key=rank)
        if rank({"metrics": metrics}) <= rank(weakest):
            return False
        active.remove(weakest)
        history_append("demoted", weakest, weakest.get("metrics"), "evicted by stronger")
    entry = {**spec, "metrics": metrics, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    active.append(entry)
    _save_active(active)
    history_append("promoted", entry, metrics, reason)
    return True


def demote(factor_id, reason="auto"):
    active = load_active()
    keep = [a for a in active if a.get("id") != factor_id]
    if len(keep) == len(active):
        return False
    _save_active(keep)
    history_append("demoted", {"id": factor_id}, reason=reason)
    return True


def main(argv):
    if "--list" in argv:
        for a in load_active():
            print(a["id"], a.get("direction"), a.get("threshold"),
                  "oos_lo=", a.get("metrics", {}).get("oos", {}).get("wilson_lo"))
    elif "--disable" in argv:
        fid = argv[argv.index("--disable") + 1]
        note = argv[argv.index("--note") + 1] if "--note" in argv else "manual"
        ok = demote(fid, reason=f"disabled: {note}")
        print("disabled" if ok else "not found", fid)
    else:
        print("usage: --list | --disable <id> [--note ...]")


if __name__ == "__main__":
    main(sys.argv[1:])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/ton-quant/scripts && python3 desk_factors_test.py`
Expected: `ok test_*` lines then `ALL PASS`.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/ton-quant
git add scripts/desk_factors.py scripts/desk_factors_test.py
git commit -m "researcher: factor DSL interpreter + active registry + history + CLI"
```

---

### Task 2: desk_features.py — attach raw fields to tokens

Factors need the raw snapshot fields per token.

**Files:**
- Modify: `scripts/desk_features.py` (the `tok_feats` helper)

- [ ] **Step 1: Locate `tok_feats` in `build_features`**

Find:

```python
    def tok_feats(addr):
        t = snap.get(addr, {})
        return {
            "wash": token_wash(addr, wash_ban),
            "vol_auth": vol_auth(t) if t else 0.5,   # unknown -> neutral
            "conc": conc(t) if t else 0.5,
        }
```

- [ ] **Step 2: Add raw `fields` to the returned dict**

Replace with:

```python
    def tok_feats(addr):
        t = snap.get(addr, {})
        return {
            "wash": token_wash(addr, wash_ban),
            "vol_auth": vol_auth(t) if t else 0.5,   # unknown -> neutral
            "conc": conc(t) if t else 0.5,
            "fields": {k: t.get(k) for k in                 # raw snapshot fields for factors
                       ("vol24", "tvl", "holders", "buys", "sells",
                        "mcap", "supply", "price", "pools")} if t else {},
        }
```

- [ ] **Step 3: Verify features still self-check and tokens carry fields**

Run:
```bash
cd ~/Projects/ton-quant && python3 scripts/desk_features.py --check && \
python3 -c "import sys;sys.path.insert(0,'scripts');import desk_features as D;t=[x for x in D.build_features()['tokens'] if x.get('fields')][0];print('has fields:',sorted(t['fields'])[:4])"
```
Expected: the `OK ...` self-check line, then `has fields: ['buys', 'holders', 'mcap', 'pools']` (or similar non-empty subset).

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/ton-quant
git add scripts/desk_features.py
git commit -m "features: attach raw snapshot fields to token dicts (for factors)"
```

---

### Task 3: desk.py — apply active factors in token verdicts

**Files:**
- Modify: `scripts/desk.py` (`agent1`)

- [ ] **Step 1: Import desk_factors at top of desk.py**

Find:

```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_features import build_features, load  # noqa: E402
```

Replace with:

```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_features import build_features, load  # noqa: E402
import desk_factors  # noqa: E402
```

- [ ] **Step 2: Apply active factors inside agent1 (tokens only)**

Find the end of `agent1`:

```python
    if RISK_ORD[floor] > RISK_ORD[risk]:              # never below the floor
        risk = floor
    if fflag and fflag not in flags:
        flags = [fflag] + flags
    return {"manip_risk": risk, "flags": flags[:5], "reason": reason or "deterministic floor"}
```

Replace with:

```python
    if RISK_ORD[floor] > RISK_ORD[risk]:              # never below the floor
        risk = floor
    if fflag and fflag not in flags:
        flags = [fflag] + flags
    if is_token and f.get("fields"):                  # active learned factors can only RAISE
        frisk, fflags = desk_factors.apply_active(f["fields"])
        if RISK_ORD[frisk] > RISK_ORD[risk]:
            risk = frisk
        flags = flags + [x for x in fflags if x not in flags]
    return {"manip_risk": risk, "flags": flags[:5], "reason": reason or "deterministic floor"}
```

- [ ] **Step 3: Verify floors stay hard (factor cannot lower a wash-ban high)**

Run:
```bash
cd ~/Projects/ton-quant && python3 -c "
import sys; sys.path.insert(0,'scripts'); import desk
# wash-banned token + a (hypothetical) benign factor must stay high
f={'wash':1.0,'vol_auth':0.9,'conc':0.1,'fields':{'vol24':1,'tvl':100,'buys':5,'sells':5,'holders':9999}}
v=desk.agent1('qwen3-4b-4bit', f, is_token=True)
print('wash-banned ->', v['manip_risk']); assert v['manip_risk']=='high', 'floor breached!'
print('OK floors stay hard')"
```
Expected: `wash-banned -> high` then `OK floors stay hard`. (Requires Osaurus up; the LLM call still runs but the floor forces high regardless.)

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/ton-quant
git add scripts/desk.py
git commit -m "desk: apply active learned factors to token risk (max with floor, raise-only)"
```

---

### Task 4: desk_researcher.py — propose → gate → promote/revalidate

**Files:**
- Create: `scripts/desk_researcher.py`
- Test: `scripts/desk_researcher_test.py`

- [ ] **Step 1: Write the failing test (gate logic, deterministic — no LLM)**

Create `scripts/desk_researcher_test.py`:

```python
#!/usr/bin/env python3
"""Plain-assert tests for desk_researcher.gate (no LLM)."""
import desk_researcher as R

def _snaps_with_signal():
    # 10 dates; tokens with high vol_tvl (BAD) drop next day, low vol_tvl rise.
    snaps = {}
    for i in range(10):
        d = f"2026-02-{i+1:02d}"
        toks = {}
        # 'bad' token: high vol/tvl, price decays each day
        toks["BAD"] = {"vol24": 90.0, "tvl": 10.0, "price": 100.0 - i * 5}
        # 'good' token: low vol/tvl, price rises
        toks["GOOD"] = {"vol24": 5.0, "tvl": 100.0, "price": 100.0 + i * 5}
        snaps[d] = {"tokens": toks}
    return snaps

SPEC = {"id": "f_vt", "expr": {"op": "div", "a": "vol24", "b": "tvl"},
        "direction": "high_is_bad", "threshold": 3.0, "horizon": 1}

def test_gate_accepts_planted_signal():
    g = R.gate(SPEC, _snaps_with_signal(), trials=1)
    assert g is not None and g["passed"] is True, g

def test_gate_rejects_noise():
    # flat prices -> excess ~0, no significant underperformance
    snaps = {f"2026-03-{i+1:02d}": {"tokens": {"X": {"vol24": 90.0, "tvl": 10.0, "price": 100.0}}}
             for i in range(10)}
    g = R.gate(SPEC, snaps, trials=1)
    assert g is None or g["passed"] is False

def test_deflated_bar_tightens_with_trials():
    g1 = R.gate(SPEC, _snaps_with_signal(), trials=1)
    g100 = R.gate(SPEC, _snaps_with_signal(), trials=100)
    assert g100["bar"] < g1["bar"]   # more trials -> stricter

if __name__ == "__main__":
    for n, fn in sorted(globals().items()):
        if n.startswith("test_"):
            fn(); print("ok", n)
    print("ALL PASS")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/ton-quant/scripts && python3 desk_researcher_test.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'desk_researcher'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/desk_researcher.py`:

```python
#!/usr/bin/env python3
"""TON Quant v3.0 — agent-researcher (Phase 2): propose -> gate -> promote.

The LLM proposes ONE constrained-DSL factor; a deterministic walk-forward OOS gate
(reusing score.py Wilson/sign-test on forward EXCESS returns) decides if it predicts
underperformance robustly, with an anti-overfit deflated bar (stricter as the LLM
tries more factors). Survivors auto-promote into data/desk/factors_active.json with a
full append-only history. revalidate() demotes active factors that decay.

Run from repo root:
  python3 scripts/desk_researcher.py            # one propose->gate->promote pass
  python3 scripts/desk_researcher.py --revalidate
Self-test (gate only, no LLM): scripts/desk_researcher_test.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import wilson_lo, sign_test_p                       # noqa: E402
from desk_calibration import load_snaps, forward_excess        # noqa: E402
from desk_factors import (factor_signal, fires, FIELDS, DERIVED, OPS,  # noqa: E402
                          load_active, promote, demote, history_append, trials_count)
from desk import llm                                           # noqa: E402

BASE_P = 0.05
MIN_FIRED = 5          # need this many fired tokens in each split
MODEL = os.environ.get("DESK_MODEL", "qwen3-4b-4bit")


def _stats(ex):
    n = len(ex)
    losers = sum(1 for e in ex if e < 0)
    return {"n": n, "losers": losers, "wilson_lo": wilson_lo(losers, n),
            "sign_p": sign_test_p(losers, n - losers),
            "avg": round(sum(ex) / n, 4) if n else 0.0}


def _collect(spec, snaps, dates):
    ex = []
    for d in dates:
        for addr, t in (snaps[d].get("tokens", {}) or {}).items():
            if fires(spec, factor_signal(spec, t)):
                e = forward_excess(snaps, d, addr, spec.get("horizon", 7))
                if e is not None:
                    ex.append(e)
    return ex


def gate(spec, snaps, trials):
    """Walk-forward OOS gate. Returns dict(in_sample, oos, bar, passed) or None."""
    dates = sorted(snaps)
    if len(dates) < 6:
        return None
    cut = int(len(dates) * 0.6)
    si = _stats(_collect(spec, snaps, dates[:cut]))
    so = _stats(_collect(spec, snaps, dates[cut:]))
    bar = BASE_P / (trials ** 0.5 if trials > 0 else 1)
    def sig(s):                                  # majority underperform, significant, neg avg
        return (s["n"] >= MIN_FIRED and s["wilson_lo"] is not None and s["wilson_lo"] > 50.0
                and s["sign_p"] is not None and s["sign_p"] < bar and s["avg"] < 0)
    return {"in_sample": si, "oos": so, "bar": round(bar, 4),
            "passed": bool(sig(si) and sig(so))}


# ---------- LLM proposal ----------
def _research_sys(active):
    avoid = "; ".join(json.dumps(a["expr"]) for a in active) or "none"
    return (
        "You are a quant factor researcher. Propose ONE candidate factor that predicts a "
        "token's FUTURE underperformance (manipulation/dump risk) from snapshot fields: "
        + ", ".join(FIELDS + DERIVED) + ". Allowed ops: " + ", ".join(OPS) + ". expr is a tree: "
        '{"op":"div","a":<field|number|expr>,"b":<...>} (abs/const take only a/value). '
        'Reply ONLY JSON: {"id":"f_shortname","expr":{...},"direction":"high_is_bad"|'
        '"low_is_bad","threshold":<number>,"horizon":7}. Avoid these existing exprs: ' + avoid)


def propose():
    active = load_active()
    try:
        out = llm(MODEL, _research_sys(active), "Propose one new factor.")
    except Exception as e:                            # noqa: BLE001
        return None, f"llm_unavailable: {type(e).__name__}"
    if not isinstance(out, dict) or "expr" not in out:
        return None, "no expr"
    # validate it evaluates on a sample (rejects unknown fields/ops safely)
    if factor_signal(out, {k: 1.0 for k in FIELDS}) is None:
        return None, "invalid expr"
    out.setdefault("direction", "high_is_bad")
    out.setdefault("threshold", 1.0)
    out.setdefault("horizon", 7)
    out.setdefault("id", "f_" + str(abs(hash(json.dumps(out["expr"]))))[:6])
    return out, "ok"


def research_once():
    snaps = load_snaps()
    spec, why = propose()
    if not spec:
        return f"propose failed: {why}"
    history_append("proposed", spec, reason=why)
    g = gate(spec, snaps, trials_count())
    if not g:
        history_append("rejected", spec, reason="insufficient data")
        return f"rejected {spec['id']}: insufficient data"
    if g["passed"]:
        spec["metrics"] = g
        ok = promote(spec, g)
        return f"{'promoted' if ok else 'rejected(dup/weak)'} {spec['id']} oos_lo={g['oos']['wilson_lo']}"
    history_append("rejected", spec, g, "failed gate")
    return f"rejected {spec['id']}: failed gate (oos_lo={g['oos']['wilson_lo']})"


def revalidate():
    snaps = load_snaps()
    n = 0
    for a in load_active():
        g = gate(a, snaps, trials_count())
        if not g or not g["passed"]:
            demote(a["id"], reason="revalidate: decayed")
            n += 1
    return f"revalidate: demoted {n}"


def main(argv):
    print(revalidate() if "--revalidate" in argv else research_once(), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
```

- [ ] **Step 4: Run unit test to verify it passes**

Run: `cd ~/Projects/ton-quant/scripts && python3 desk_researcher_test.py`
Expected: `ok test_*` lines then `ALL PASS`.

- [ ] **Step 5: One live propose pass (needs Osaurus)**

Run: `cd ~/Projects/ton-quant && python3 scripts/desk_researcher.py`
Expected: a line like `promoted f_... oos_lo=NN` or `rejected f_...: failed gate (...)` — no traceback. Either outcome is valid (the gate is honest).

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/ton-quant
git add scripts/desk_researcher.py scripts/desk_researcher_test.py
git commit -m "researcher: LLM propose -> walk-forward OOS gate (deflated bar) -> auto-promote"
```

---

### Task 5: desk_worker.py — research/revalidate task-runners

**Files:**
- Modify: `scripts/desk_worker.py`

- [ ] **Step 1: Import the researcher**

Find:

```python
import desk                                     # noqa: E402
import desk_calibration                         # noqa: E402
```

Replace with:

```python
import desk                                     # noqa: E402
import desk_calibration                         # noqa: E402
import desk_researcher                          # noqa: E402
```

- [ ] **Step 2: Add a revalidate cadence constant**

Find:

```python
CALIB_EVERY = 6 * 3600       # recompute calibration at most this often
```

Add below it:

```python
REVALIDATE_EVERY = 12 * 3600  # re-validate active factors at most this often
```

- [ ] **Step 3: Update the picker (research after deep_vetting; revalidate by timer)**

Find:

```python
def pick_task(today_done, calib_stale, deep_pending):
    if not today_done:
        return "daily_verdicts"
    if calib_stale:
        return "calibrate"
    if deep_pending > 0:
        return "deep_vetting"
    return None
```

Replace with:

```python
def pick_task(today_done, calib_stale, deep_pending, revalidate_due=False):
    if not today_done:
        return "daily_verdicts"
    if calib_stale:
        return "calibrate"
    if revalidate_due:
        return "revalidate"
    if deep_pending > 0:
        return "deep_vetting"
    return "research"          # idle-filler: never out of work (always a factor to try)
```

- [ ] **Step 4: Add the two task-runners**

Find:

```python
def run_calibrate(state):
    desk_calibration.main()
    state["last_calib"] = int(time.time())
    return "calibrate done"
```

Add below it:

```python
def run_research(state):
    return desk_researcher.research_once()


def run_revalidate(state):
    state["last_revalidate"] = int(time.time())
    return desk_researcher.revalidate()
```

- [ ] **Step 5: Wire the runners + revalidate timer into `iterate`**

Find:

```python
    calib_stale = time.time() - state.get("last_calib", 0) > CALIB_EVERY
    v = load("data/desk/verdicts.json", {})
    deep_pending = len(v.get("tokens", [])) if today_done else 0
    task = pick_task(today_done, calib_stale, deep_pending)
    try:
        if task == "daily_verdicts":
            msg = run_daily_verdicts()
        elif task == "calibrate":
            msg = run_calibrate(state)
        elif task == "deep_vetting":
            msg = run_deep_vetting(state)
        else:
            msg = "idle: nothing due"
```

Replace with:

```python
    calib_stale = time.time() - state.get("last_calib", 0) > CALIB_EVERY
    revalidate_due = time.time() - state.get("last_revalidate", 0) > REVALIDATE_EVERY
    v = load("data/desk/verdicts.json", {})
    deep_pending = len(v.get("tokens", [])) if today_done else 0
    task = pick_task(today_done, calib_stale, deep_pending, revalidate_due)
    try:
        if task == "daily_verdicts":
            msg = run_daily_verdicts()
        elif task == "calibrate":
            msg = run_calibrate(state)
        elif task == "revalidate":
            msg = run_revalidate(state)
        elif task == "deep_vetting":
            msg = run_deep_vetting(state)
        elif task == "research":
            msg = run_research(state)
        else:
            msg = "idle: nothing due"
```

- [ ] **Step 6: Fix the final-sleep branch (task is never None now)**

Find:

```python
    return dec["sleep"] if task else 300              # nothing due -> longer sleep
```

Replace with:

```python
    return dec["sleep"]                               # research is the idle-filler
```

- [ ] **Step 7: Update the worker test for the new picker signature**

In `scripts/desk_worker_test.py`, find:

```python
def test_pick_task_prioritizes_daily_then_calibrate_then_deep():
    assert W.pick_task(today_done=False, calib_stale=True, deep_pending=5) == "daily_verdicts"
    assert W.pick_task(today_done=True, calib_stale=True, deep_pending=5) == "calibrate"
    assert W.pick_task(today_done=True, calib_stale=False, deep_pending=5) == "deep_vetting"
    assert W.pick_task(today_done=True, calib_stale=False, deep_pending=0) is None
```

Replace with:

```python
def test_pick_task_priority_order():
    assert W.pick_task(False, True, 5) == "daily_verdicts"
    assert W.pick_task(True, True, 5) == "calibrate"
    assert W.pick_task(True, False, 5, revalidate_due=True) == "revalidate"
    assert W.pick_task(True, False, 5) == "deep_vetting"
    assert W.pick_task(True, False, 0) == "research"   # idle-filler, never None
```

- [ ] **Step 8: Run worker tests**

Run: `cd ~/Projects/ton-quant/scripts && python3 desk_worker_test.py`
Expected: `ok test_*` then `ALL PASS`.

- [ ] **Step 9: Commit**

```bash
cd ~/Projects/ton-quant
git add scripts/desk_worker.py scripts/desk_worker_test.py
git commit -m "worker: research + revalidate task-runners (research is the idle-filler)"
```

---

### Task 6: Live integration + reactivate daemon

**Files:** none (verification) + reload launchd agent.

- [ ] **Step 1: Full test sweep**

Run:
```bash
cd ~/Projects/ton-quant/scripts && for t in desk_factors_test desk_researcher_test desk_worker_test desk_calibration_test; do echo "== $t =="; python3 $t.py || break; done
```
Expected: every suite prints `ALL PASS`.

- [ ] **Step 2: One worker pass that lands on research**

Run:
```bash
cd ~/Projects/ton-quant && rm -f data/desk/worker_state.json && \
python3 -c "
import sys; sys.path.insert(0,'scripts'); import desk_worker as W
# force the research branch directly
import desk_researcher as R; print(R.research_once())"
```
Expected: a `promoted ...` or `rejected ...` line, no traceback. Check `data/desk/factors_history.json` exists:
```bash
cd ~/Projects/ton-quant && python3 -c "import json;h=json.load(open('data/desk/factors_history.json'));print('history entries:',len(h),'| last:',h[-1]['action'])"
```
Expected: `history entries: N | last: proposed|promoted|rejected`.

- [ ] **Step 3: Confirm CLI override works**

Run:
```bash
cd ~/Projects/ton-quant && python3 scripts/desk_factors.py --list
```
Expected: prints active factors (possibly empty if none promoted yet — that's fine).

- [ ] **Step 4: Reload the 24/7 daemon (picks up new code)**

Run:
```bash
launchctl load ~/Library/LaunchAgents/com.tonquant.worker.plist
sleep 14
launchctl list | grep tonquant.worker
tail -5 ~/Library/Logs/tonquant-worker.log
```
Expected: agent has a PID; log shows recent task lines (`[research]`/`[deep_vetting]`/`[calibrate]`).

- [ ] **Step 5: Commit any data/desk artifacts**

```bash
cd ~/Projects/ton-quant
git add data/desk
git commit -m "researcher: first factor history + active set" || echo "nothing to commit"
git pull --rebase --autostash origin main && git push origin main
```

---

## Self-Review

**Spec coverage:**
- §2 DSL (whitelist, no exec, div0→0) → Task 1 (`eval_expr`), tested. ✓
- §3 gate (walk-forward OOS, Wilson/sign-test from score.py, deflated bar) → Task 4 (`gate`), tested (planted signal passes, noise fails, bar tightens). ✓
- §4 auto-promote + history + cap + demote + CLI override → Task 1 (`promote`/`demote`/`history_append`/`--disable`). ✓
- §5 safety: floors hard, `max(floor,factor)`, raise-only → Task 3 (verified floors-stay-hard test). ✓
- §6 worker runners `research`/`revalidate` + priority → Task 5. ✓
- §7 desk integration (`apply_active` in agent1) + raw fields → Tasks 2, 3. ✓
- §9 tests → Tasks 1, 4 suites + Task 6 sweep. ✓

**Placeholder scan:** none — all code complete, commands have expected output. ✓

**Type consistency:** `gate(spec, snaps, trials)` identical in test/impl/worker; returns `{in_sample, oos, bar, passed}` and Task 4 reads `g["oos"]["wilson_lo"]`, `g["passed"]`, `g["bar"]` consistently. `apply_active(fields, active=None) -> (risk, flags)` identical in test (Task 1) and use (Task 3). `pick_task(today_done, calib_stale, deep_pending, revalidate_due=False)` matches updated test (Task 5 Step 7) and `iterate` call. `promote(spec, metrics, reason)`/`demote(id, reason)`/`history_append(action, factor, metrics, reason)` consistent across desk_factors and desk_researcher. `FIELDS`/`DERIVED`/`OPS` imported from desk_factors into desk_researcher. ✓
```
