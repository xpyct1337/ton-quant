# Vetted Copy-Trading Implementation Plan (Phase 3)

> Steps use checkbox syntax. TDD, conytail, frequent commits.

**Goal:** A worker-run deterministic book that compares copying ALL roster wallets vs only desk-vetted (`copy_ok`) ones, proving the imitation-penalty cure in PnL terms.

**Architecture:** `desk_copytrade.py` reuses `desk_features.first_entries` (copy signals) + `desk_calibration.forward_excess` (outcomes); pure `book_stats`/`build_signals` are unit-tested. Runs inside the worker's `calibrate` task (deterministic, cheap — no new picker branch). Cloud `paper.py` untouched. Surfaced on `/desk`.

**Pre-work:** worker is running; unload before editing its source.
```bash
launchctl unload ~/Library/LaunchAgents/com.tonquant.worker.plist
```

---

### Task 1: desk_copytrade.py + test

**Files:** Create `scripts/desk_copytrade.py`, `scripts/desk_copytrade_test.py`

- [ ] **Step 1: failing test** — `scripts/desk_copytrade_test.py`:

```python
#!/usr/bin/env python3
"""Plain-assert tests for desk_copytrade (run with python3)."""
import desk_copytrade as C

def test_book_stats():
    s = C.book_stats([0.1, -0.2, 0.3])
    assert s["n"] == 3 and abs(s["total"] - 0.2) < 1e-9
    assert s["win_rate"] == round(100 * 2 / 3, 1) and abs(s["avg"] - 0.2 / 3) < 1e-9

def test_book_stats_empty():
    s = C.book_stats([])
    assert s == {"n": 0, "avg": 0.0, "win_rate": 0.0, "total": 0.0}

def test_build_signals_filters_copyok():
    # wA entered TOK@d0, wB entered BAD@d0; only wA is copy_ok
    first = {"wA": {"TOK": "2026-02-01"}, "wB": {"BAD": "2026-02-01"}}
    snaps = {"2026-02-01": {"tokens": {"TOK": {"price": 1.0}, "BAD": {"price": 1.0}}},
             "2026-02-02": {"tokens": {"TOK": {"price": 1.2}, "BAD": {"price": 0.8}}}}
    sigs = C.build_signals(first, {"wA", "wB"}, snaps, {"wA"}, horizon=1)
    assert len(sigs) == 2                                   # both have forward data
    desk = [s for s in sigs if s["copy_ok"]]
    assert len(desk) == 1 and desk[0]["wallet"] == "wA"

if __name__ == "__main__":
    for n, fn in sorted(globals().items()):
        if n.startswith("test_"):
            fn(); print("ok", n)
    print("ALL PASS")
```

- [ ] **Step 2: run, expect fail** — `cd ~/Projects/ton-quant/scripts && python3 desk_copytrade_test.py` → `ModuleNotFoundError`.

- [ ] **Step 3: implement** — `scripts/desk_copytrade.py`:

```python
#!/usr/bin/env python3
"""TON Quant v3.0 — vetted copy-trading book (Phase 3, working-product proof).

Compares copying ALL roster wallets vs only desk-vetted (copy_ok) ones, using only
existing data: copy signal = a roster wallet's FIRST entry into a token
(desk_features.first_entries); outcome = forward EXCESS return (desk_calibration).
Deterministic, no LLM, no new fetches. Cloud paper.py untouched.

Run from repo root. Self-check: python3 scripts/desk_copytrade.py --check
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_features import load, first_entries          # noqa: E402
from desk_calibration import load_snaps, forward_excess  # noqa: E402

HORIZON = 3   # short: dated wallet history is only a few days


def book_stats(exs):
    n = len(exs)
    if not n:
        return {"n": 0, "avg": 0.0, "win_rate": 0.0, "total": 0.0}
    wins = sum(1 for e in exs if e > 0)
    return {"n": n, "avg": round(sum(exs) / n, 4),
            "win_rate": round(100 * wins / n, 1), "total": round(sum(exs), 4)}


def build_signals(first, roster_addrs, snaps, copyok, horizon):
    """One signal per (roster wallet, token first-entry) with a forward outcome."""
    sigs = []
    for w, toks in first.items():
        if w not in roster_addrs:
            continue
        for taddr, date in toks.items():
            ex = forward_excess(snaps, date, taddr, horizon)
            if ex is not None:
                sigs.append({"wallet": w, "token": taddr, "date": date,
                             "ex": ex, "copy_ok": w in copyok})
    return sigs


def build_copytrade():
    snaps = load_snaps()
    roster = {w["addr"] for w in (load("data/wallets.json", {}) or {}).get("roster", [])}
    verdicts = load("data/desk/verdicts.json", {}) or {}
    copyok = {w["addr"] for w in verdicts.get("wallets", []) if w.get("copy_ok")}
    sigs = build_signals(first_entries(), roster, snaps, copyok, HORIZON)
    allb = book_stats([s["ex"] for s in sigs])
    deskb = book_stats([s["ex"] for s in sigs if s["copy_ok"]])
    edge = round(deskb["avg"] - allb["avg"], 4)
    note = ("desk vetoed all wallets; copy_all avg %.4f avoided" % allb["avg"]
            if deskb["n"] == 0 else "")
    return {"horizon": HORIZON, "copyok_wallets": len(copyok),
            "copy_all": allb, "copy_desk": deskb, "edge": edge, "note": note}


def main():
    ct = build_copytrade()
    os.makedirs("data/desk", exist_ok=True)
    with open("data/desk/copytrade.json", "w") as f:
        json.dump(ct, f, ensure_ascii=False, indent=2)
    chk = json.load(open("data/desk/copytrade.json"))   # read-back
    print(f"copytrade: all n={chk['copy_all']['n']} avg={chk['copy_all']['avg']} | "
          f"desk n={chk['copy_desk']['n']} avg={chk['copy_desk']['avg']} | "
          f"edge={chk['edge']} {chk['note']}", flush=True)


def _check():
    ct = build_copytrade()
    for b in ("copy_all", "copy_desk"):
        assert set(ct[b]) == {"n", "avg", "win_rate", "total"}, f"bad book {b}"
        assert ct[b]["n"] >= 0
    assert ct["copy_desk"]["n"] <= ct["copy_all"]["n"], "desk book not subset"
    print("OK", {"all": ct["copy_all"], "desk": ct["copy_desk"], "edge": ct["edge"]})


if __name__ == "__main__":
    _check() if "--check" in sys.argv else main()
```

- [ ] **Step 4: run test, expect PASS** — `cd ~/Projects/ton-quant/scripts && python3 desk_copytrade_test.py`.
- [ ] **Step 5: live self-check** — `cd ~/Projects/ton-quant && python3 scripts/desk_copytrade.py --check`.
- [ ] **Step 6: commit** — `git add scripts/desk_copytrade.py scripts/desk_copytrade_test.py && git commit -m "copytrade: vetted vs all copy-trading book (deterministic)"`

---

### Task 2: run copytrade inside the worker's calibrate task

**Files:** Modify `scripts/desk_worker.py`

- [ ] **Step 1: import** — after `import desk_researcher` add `import desk_copytrade  # noqa: E402`.
- [ ] **Step 2: extend run_calibrate** — replace:

```python
def run_calibrate(state):
    desk_calibration.main()
    state["last_calib"] = int(time.time())
    return "calibrate done"
```

with:

```python
def run_calibrate(state):
    desk_calibration.main()
    desk_copytrade.main()                  # deterministic analytics, same cadence
    state["last_calib"] = int(time.time())
    return "calibrate+copytrade done"
```

- [ ] **Step 3: worker tests still pass** — `cd ~/Projects/ton-quant/scripts && python3 desk_worker_test.py`.
- [ ] **Step 4: commit** — `git add scripts/desk_worker.py && git commit -m "worker: run copytrade alongside calibrate"`

---

### Task 3: /desk tile + data.js loader

**Files:** Modify `app/src/lib/data.js`, `app/src/routes/desk/+page.svelte`

- [ ] **Step 1: data.js loader** — after `loadDeskFactors` add:

```javascript
// AI Desk copy-trading proof: vetted (copy_ok) vs all-roster forward returns.
export async function loadDeskCopytrade() {
  return j(`${RAWB}/desk/copytrade.json`).catch(() => null);
}
```

- [ ] **Step 2: import + load** — in `+page.svelte` add `loadDeskCopytrade` to the import; add `let copytrade = $state(undefined);`; in `onMount` add `copytrade = await loadDeskCopytrade();`.

- [ ] **Step 3: tile** — insert before the model card (`<i class="ti ti-cpu"></i> Модель LLM`):

```svelte
<section class="card">
  <div class="ttl"><i class="ti ti-arrows-split"></i> Copy-trading: вётчено vs всё</div>
  {#if copytrade === undefined}
    <div class="muted pad">Загружаю…</div>
  {:else if !copytrade}
    <div class="muted">Ещё не посчитано (появится после прогона воркера). Сравнивает копирование всех roster-кошельков против только <code>copy_ok</code>-вётченных.</div>
  {:else}
    <div class="muted small">forward excess на +{copytrade.horizon}д. Сигнал = первый вход кошелька в токен. Вётчено кошельков: {copytrade.copyok_wallets}.</div>
    <div class="kpis">
      <div class="kpi"><span class="kl">copy-all n / avg</span><span class="kv">{copytrade.copy_all.n} / <span class={copytrade.copy_all.avg < 0 ? 'down' : 'up'}>{(copytrade.copy_all.avg * 100).toFixed(1)}%</span></span></div>
      <div class="kpi"><span class="kl">copy-desk n / avg</span><span class="kv">{copytrade.copy_desk.n} / <span class={copytrade.copy_desk.avg < 0 ? 'down' : 'up'}>{(copytrade.copy_desk.avg * 100).toFixed(1)}%</span></span></div>
      <div class="kpi"><span class="kl">edge (desk−all)</span><span class="kv" class:up={copytrade.edge >= 0} class:down={copytrade.edge < 0}>{(copytrade.edge * 100).toFixed(1)}%</span></div>
    </div>
    {#if copytrade.note}<div class="muted small">{copytrade.note}</div>{/if}
  {/if}
</section>
```

- [ ] **Step 4: commit** — `git add app/src/lib/data.js app/src/routes/desk/+page.svelte && git commit -m "desk vitrina: copy-trading vetted-vs-all tile"`

---

### Task 4: live verify + reactivate daemon + push

- [ ] **Step 1: full sweep** — run all `scripts/*_test.py` suites; each `ALL PASS`.
- [ ] **Step 2: live copytrade** — `python3 scripts/desk_copytrade.py` → a summary line, no traceback.
- [ ] **Step 3: reload daemon** — `launchctl load ~/Library/LaunchAgents/com.tonquant.worker.plist; sleep 12; tail -4 ~/Library/Logs/tonquant-worker.log`.
- [ ] **Step 4: push** — `git pull --rebase --autostash origin main && git push origin main` (triggers deploy for app/ change).

## Self-Review
- Spec mechanism (first_entries → forward_excess → two books) → Task 1. ✓
- Worker integration (calibrate cadence) → Task 2. ✓
- Vitrina → Task 3. ✓
- copy_desk ⊆ copy_all asserted (`_check`, test). ✓
- Types: `book_stats(exs)->{n,avg,win_rate,total}`, `build_signals(first,roster,snaps,copyok,horizon)->[{wallet,token,date,ex,copy_ok}]` consistent test/impl. ✓
- No placeholders. ✓
