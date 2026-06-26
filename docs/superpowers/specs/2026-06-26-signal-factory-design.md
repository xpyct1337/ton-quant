# Signal Factory — design spec (2026-06-26)

## Problem & goal

The current perp signal bot (`scripts/signal_bot.py`) has one promising-but-thin lead: 4H pullback-in-uptrend + GBM meta-filter + Coinalyze microstructure → PF 2.03, +1.23%/trade, but only **28 out-of-sample trades**. Igor wants to scale signal/trade count by **100–1000×** and surface more opportunities, while staying verify-first (don't ship a mirage).

Goal: turn the single hand-coded strategy into a **signal factory** that generates a large candidate pool, filters it with one meta-model, and only counts a trade as real after it clears two gates — an overfit test (CPCV/PBO) and a fee-aware paper-equity sim. Trade count scales by `universe × timeframes × primaries × sides`; the gates keep the explosion honest.

## The binding constraint: fees, not ideas

Generating more candidates is trivial. The real limit is cost. Today's edge is +1.23%/trade at 4H; OKX perp taker round-trip ≈ 0.10% + funding over hold — comfortably cleared. As frequency rises, move-per-bar shrinks while fees stay fixed, so edge/trade falls toward the fee floor. **Rule: raise frequency only while fee-aware expectancy stays positive.** This rule, not a target number, decides how far we scale.

## Trade-count math (vs current 10-asset / 4H / long-only / 1-primary)

| Lever | Multiplier |
|---|---|
| Universe 10 → ~150 liquid perps (of 386 live OKX USDT perps) | ×15 |
| Both sides (long + short) | ×2 |
| 4H → 1H | ×4 |
| 4H → 15m | ×16 |
| 3 primaries | ×3 |

~120× at 1H, ~960× at 15m — reachable mainly via universe × frequency.

## Architecture — units with one purpose each

1. **Universe selector** — pick liquid perps by rolling turnover threshold from OKX `instruments` + tickers. In: min-turnover, max-N. Out: list of instIds. (New perp module; do not tangle with the existing TON-token `universe.py`.)
2. **Data layer** — OHLCV fetch+cache per `(asset, timeframe)`; Coinalyze funding/OI/liquidations per asset. Extends the existing `BAR`-parametrized `fetch`/`load`; adds timeframe to cache keys.
3. **Primary generators** — pluggable `primary(df, ctx) -> list[Candidate]`. Each is deliberately high-recall, low-precision (e.g. pullback-in-uptrend, breakout-retest, liquidation-flush reversal). Long and short variants. The meta-model does the precision.
4. **Labeler** — triple-barrier (ATR TP/SL + time). For *training* the meta-model, overlapping candidates are allowed (decouples training-sample count from tradeable-trade count). For *equity*, non-overlapping per asset.
5. **Feature builder** — independent features only: one mean-reversion stretch, trend/regime, ATR%, relative strength vs BTC, funding, OI change, liquidation flush/skew, plus cross-sectional rank features. No collinear stacking.
6. **Meta-model** — one `HistGradientBoostingClassifier` over the whole pool (more data ⇒ better filter). Take-threshold learned on train only.
7. **Gate A — CPCV/PBO** — Combinatorial Purged Cross-Validation with embargo → a *distribution* of OOS PF plus Probability of Backtest Overfitting. Replaces the single walk-forward. Want PBO well below 0.5.
8. **Gate B — fee-aware vol-target equity** — position sized so each trade risks a constant fraction of equity (size from ATR stop distance); equity net of taker fees, slippage assumption, and funding over hold. Produces the equity curve + per-stage report card.
9. **Regime detector** — classify trend-up / down / range / vol-spike (EMA200 slope + ADX + realized-vol percentile). Used as a feature and an optional hard gate.
10. **Reporter** — per-stage OOS card: trades, expectancy (gross & net), PF distribution, PBO, max DD.

Data flow: `universe → data → primaries(×sides) → label → features → meta-model (CPCV) → fee-aware equity → report`.

## Staged scale-up (gate every stage)

- **Stage A — universe at 4H (~30×).** 10 → ~150 perps + both sides, same proven 4H timeframe. Validates cross-sectional breadth where the edge is proven and fees are cleared. Pass = CPCV PBO low and net expectancy positive.
- **Stage B — add 1H (~120×).** Only if A passes. Confirm net edge survives the 4× frequency bump.
- **Stage C — add 15m + a 2nd primary (~1000×).** Only if B passes. Stop adding frequency the moment fee-aware expectancy goes negative.

Each stage is a gate, not a milestone to rush past. Appetite = verify-first.

## How the four chosen workstreams map in

- Short side + more trades → candidate generation (sides) + universe + frequency.
- Regime gate + new features → regime detector + feature builder feeding the factory.
- Overfit tests (CPCV/PBO) → Gate A.
- Vol-target sizing + paper equity → Gate B.

## Testing & verification

- Leakage guards as asserts: signals time-sorted; CPCV purge+embargo enforced; no feature uses future bars.
- One runnable self-check on non-trivial logic (conytail): triple-barrier label and vol-target sizing math verified on inline data (`__main__` asserts). Fee-aware equity reproducible from cache.
- Sanity: net expectancy must be reported alongside gross everywhere; a stage cannot "pass" on gross numbers.

## Risks & mitigations

- **Fee floor at high frequency** → net-of-fee gate at every stage; stop scaling when it turns negative.
- **Overfit from many primaries/features** → CPCV/PBO; keep features independent; prefer few primaries.
- **Cross-asset correlation** (many simultaneous correlated longs = concentrated risk) → vol-target sizing + cap on concurrent same-direction exposure.
- **Data volume / rate limits** across ~150 assets × intraday → cache aggressively, batch Coinalyze multi-symbol calls, paginate within limits.
- **Mount truncation** (QUANT/OneDrive) → verify every write tail with the Read tool; run logic self-checks in the sandbox, never trust bash reads of repo files.

## Out of scope (YAGNI for now)

Live trading / order routing; Telegram publishing (deferred — appetite is verify-first); sub-5m HFT and latency infra; order-book / L2 microstructure; portfolio optimization beyond vol-target + exposure cap.
