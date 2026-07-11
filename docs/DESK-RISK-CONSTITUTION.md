# Desk Risk Constitution

Operator-facing risk contract for the AI Smart-Money **Desk** and its paper bots.
This is the single place that states what the system is *allowed* to do, the
numeric limits it operates under, and the hard rules an LLM cannot override.
It complements the design spec (`docs/V3.0-AI-SMART-MONEY-DESK.md`) — the spec
explains *why*, this document is the enforceable *what*.

> Not financial advice. Nothing here authorizes trading with real funds.

## 0. Status: advisory + paper only — no live execution

**The Desk does not place, sign, or broadcast any real on-chain order.** There is
no wallet key material, no chain/DEX client, and no order-submission path anywhere
in the codebase. A repo-wide search for `mnemonic` / `private_key` /
`sign_transaction` / `broadcast` / `send_transaction` / `place_order` / TON SDK
clients returns zero hits in any desk file. What the system produces:

| Component | Output | Nature |
|---|---|---|
| `scripts/desk.py` | `data/desk/verdicts.json` — per wallet/token `{manip_risk, flags, copy_ok, conviction, reason}` | Risk **ratings** consumed by the static dashboard |
| `scripts/paper.py` | `data/paper/bots.json` — TON bot equity curves | **Simulated** fills (modeled fee + price-impact), never sent |
| `scripts/altpaper.py` | `data/paper/altbots.json` — CEX-major bot equity curves | **Simulated** fills (flat taker fee), never sent |

Every "trade" is a JSON mutation. Consequently, the operational controls a live
autonomous trader needs — a single order choke-point, a global kill-switch, a
human approval queue, an explicit arm/disarm flag — are **intentionally not
built** (see §4). They only become meaningful once a real execution module
exists, and none does.

## 1. Numeric limits (paper layer)

These live as code constants today; this table is the authoritative mirror.
Source of truth stays the code — when a constant changes, update this row too.

### TON paper bot — `scripts/paper.py`

| Limit | Const | Value | Meaning |
|---|---|---|---|
| Starting cash | `START_CASH` | `1000.0` | Per-bot simulated capital |
| Taker fee | `FEE` | `0.003` | Per-leg cost |
| Max price impact | `IMPACT_CAP` | `0.01` | Position capped so modeled slippage ≤ 1% of TVL |
| Volume-scale floor | `MIN_VSCALE` | `0.3` | Lower bound on turnover-based size scaling |
| Min position | `MIN_POS` | `25.0` | Below this, no entry is opened |
| Min effective weight | `MIN_EFF_W` | `0.5` | Candidate admission threshold |

Per-bot caps (`BOTS` dict, `scripts/paper.py`):

| Bot | `pos` | `max_open` | `sig_cap` | `min_tvl` | `min_holders` | `min_liq_ratio` |
|---|---|---|---|---|---|---|
| `cons` | 100.0 | 6 | 2 | 50000 | 5000 | 0.02 |
| `aggr` | 90.0 | 12 | 3 | 20000 | 500 | 0.0 |

`sig_cap` bounds how many open positions may share one signal (diversification).
Sizing is edge-scaled and capped at `≤1.0×`; non-positive measured edge → size 0.

### CEX-major paper bot — `scripts/altpaper.py`

| Limit | Value |
|---|---|
| Starting cash | `1000.0` |
| Position (`pos`) | `500.0` |
| Max concurrent (`max_open`) | `2` |
| Taker fee | `0.001` |
| TP / SL / max hold | `+0.20` / `-0.10` / 5 days |

## 2. Hard rules the LLM cannot override

The Desk uses LLMs for judgment, but safety is structural, not prompt-dependent.
A model failure falls back to the conservative deterministic path — never to a
riskier one.

1. **Deterministic risk floor, one-directional.** `floor_risk()` classifies risk
   from wash/vol-auth/co-entry/concentration; `wash ≥ 0.5 → high`. The LLM may
   only *raise* risk above the floor, never lower it (`scripts/desk.py`,
   `floor_risk()` and the floor-enforcement in the agent step).
2. **Copy hard-block.** A wallet with `manip_risk = high`, a thin sample, or no
   supporting evidence is forced to `copy_ok = false` (`scripts/desk.py`,
   `agent2()`). High risk is never copy-eligible.
3. **Learned factors can only RAISE risk.** `apply_active()` never lowers a
   verdict (`scripts/desk_factors.py`). A learned factor cannot make a wallet
   look safer than the deterministic floor.
4. **Statistical gate on factor promotion.** New factors pass a walk-forward OOS
   gate (Wilson/sign test with an anti-overfit deflated bar) before going active
   (`scripts/desk_researcher.py`, `gate()`); the LLM cannot bypass it.
5. **Wash-trade entry ban (paper).** A token with `vol/tvl > 3` is banned from
   new entries for 7 days (`scripts/paper.py`).
6. **Compute governor.** The 24/7 worker sleeps on battery / thermal throttle
   (`scripts/desk_worker.py`, `power_state()` / `thermal_decision()`). This
   governs compute, not exposure.

## 3. Auditability

There is no human approval queue; instead every control change is recorded and
reversible:

- **Append-only factor history** — proposed/promoted/demoted/rejected with metrics
  (`scripts/desk_factors.py`, `history_append()` → `data/desk/factors_history.json`,
  ring buffer of 1000).
- **Scoped auto-commit** — the worker commits only `data/desk` and never touches
  `app/` or repo root (`scripts/desk_worker.py`, `maybe_commit()`).
- **Manual override** — an operator can kill a factor via
  `python scripts/desk_factors.py --disable <id> [--note ...]`.

## 4. Deliberately NOT built (decision record)

To keep the system honest under YAGNI (`AGENTS.md`), the following are **out of
scope** as long as there is no real-execution module. Do not add them speculatively;
add them only alongside a live-order path, and revisit this whole document then.

| Control | Why omitted |
|---|---|
| Single order choke-point module | No real orders exist to funnel |
| Global trading kill-switch | Nothing to switch off; per-asset wash-ban already gates paper entries |
| Human approval queue | Replaced by statistical gate + append-only audit log + manual `--disable` |
| Explicit arm/disarm flag | System is permanently non-trading by architecture, not by a boolean |

The moment real on-chain execution is proposed, all four move from "omitted" to
"required", and this constitution must gain hard numeric limits for live exposure
(max position, max daily loss, global kill conditions) before any funds are at risk.
