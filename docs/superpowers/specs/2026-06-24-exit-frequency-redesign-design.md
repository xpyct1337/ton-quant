# Exit Redesign + Aggressive Frequency — Design

Date: 2026-06-24
Scope: `scripts/paper.py` (+ `scripts/universe.py` for TRACKED). Daily cadence unchanged.

## Problem

Entries are good; exiting in profit is hard. The current exit set can only bank a
win by hitting the full fixed TP (+15% cons / +30% aggr). If a position runs to
e.g. +12% and fades, the time-stop or SL closes it at the current market price —
often flat or red. There is no trailing stop and no break-even stop. Igor's ask:
"exit in profit, at worst break-even (around entry)." Second ask: trade more often.

## Current exit logic (`run_bot`, per position per daily snapshot)

Order: `rug_exit` (dtvl < −25%) → `tp` (ret ≥ cfg.tp) → `edge_fade` (size mult == 0)
→ `sl` (ret ≤ cfg.sl) → `time` (days ≥ max_days, **at market price**).

Frequency drivers: daily cadence (signals are day-over-day deltas), `TRACKED=100`
universe, `detect_signals` thresholds, bot filters (min_tvl/min_holders), and the
action caps `max_open` (3/6), `MIN_EFF_W=1.0`, edge-gate zeroing size.

## Chosen approach: A — layered protective exits + cheap aggressive frequency

Rejected: B (ATR/volatility stops + partial scaling) — over-engineered for current
data depth, needs fractional-position state; revisit once base is validated.
Rejected: C (intraday cadence) — rewrites delta logic + scheduler + API load; out
of scope, noted as the next frontier.

### Exit ladder (new)

Add one per-position field: `peak` (max price seen since entry; init = entry_eff).
Each snapshot: `cur` = price, update `peak = max(peak, cur)`,
`ret = cur/entry_eff − 1`, `peak_ret = peak/entry_eff − 1`. Evaluate in order:

1. `rug_exit` — dtvl < −25% (unchanged hard safety).
2. `trail` — `peak_ret ≥ TRAIL_ARM` AND `ret ≤ peak_ret − TRAIL_GAP` → exit.
   Rides winners without needing the fixed TP.
3. `breakeven` — `peak_ret ≥ BE_ARM` AND `ret ≤ BE_FLOOR` → exit. A position that
   ran up never closes red. BE_FLOOR covers fees so "break-even" is truly ≥ 0.
4. `edge_fade` — size mult == 0 AND `ret ≤ 0` → exit. Only fade losers; winners are
   handled by trail.
5. `sl` — `ret ≤ cfg.sl` → exit. Active only before BE arms; once `peak_ret ≥ BE_ARM`
   the BE floor (step 3) is higher and fires first.
6. `tp` — `ret ≥ cfg.tp` → exit. Upper "take it and run" cap.
7. `time` — days ≥ max_days: if `ret > 0` exit `time`; else if trend alive
   (`d1 > 0` or `dtvl > 0`) hold but never beyond `2 × max_days`; else exit `time`.

Per-bot parameters:

| bot  | BE_ARM | BE_FLOOR | TRAIL_ARM | TRAIL_GAP | tp (cap) | sl    | max_days |
|------|--------|----------|-----------|-----------|----------|-------|----------|
| cons | +5%    | +0.5%    | +10%      | 5%        | 25%      | −7%   | 5        |
| aggr | +8%    | +1%      | +15%      | 10%       | 50%      | −12%  | 3        |

(tp raised from 15/30 to 25/50 so trailing, not the cap, governs most winners.
sl/max_days unchanged.)

### Risk diversification

Per-signal-type open cap: at entry, skip a candidate if the bot already holds
`SIG_CAP` positions opened on that same signal type. cons = 2, aggr = 3. Keeps the
portfolio spread across ≥3–4 detectors even at full slots. Existing edge+impact
position sizing is retained.

### Aggressive frequency (daily cadence kept)

- `max_open`: cons 3 → 6, aggr 6 → 12.
- `TRACKED`: 100 → 200 (`universe.py`) — track the full discovered universe.
- `MIN_EFF_W`: 1.0 → 0.5 — admit more candidates; safe because exits now protect.
- base `pos`: aggr 150 → 90 so 12 slots fit ~$1000 (12×90≈1080; sizing shrinks to
  fit cash). cons stays 100 (6×100=600).
- `detect_signals` thresholds and edge-gate size floor unchanged — entry quality
  is the core and is preserved. Cash remains the real binding constraint on slot
  fill; sizing already adapts.

## Data flow / compatibility

- New field `peak` on position dicts. Existing open positions in
  `data/paper/bots.json` lack it → on load, default `peak = entry_eff` (no crash,
  trailing simply needs one more snapshot to arm). Handle with `p.get("peak",
  p["entry_eff"])`.
- New close `reason` values: `trail`, `breakeven`. Journals/trades already store
  `reason` as a free string; dashboards that group by reason gain two buckets.
- `score.py` unaffected — it scores detected signals, not exits.

## Testing / verification

- Extend `scripts/score_test.py` style unit checks (stdlib) for the exit ladder:
  break-even arms then protects; trailing arms and captures a faded winner; smart
  time-stop holds a trending loser then exits; SL only before BE arms; per-signal
  cap blocks the 3rd/4th same-signal entry.
- Replay: run `paper.py` over existing snapshots and compare trade log win-rate,
  avg ret, and count of red exits-after-green before/after. Expect: fewer
  green→red round-trips, more `trail`/`breakeven` closes, more total trades.
- conytail check: no new deps, minimal new state (one field), config-only frequency.

## Out of scope

Partial/scaled exits (B), intraday cadence (C), loosening detection thresholds,
real-money execution.
