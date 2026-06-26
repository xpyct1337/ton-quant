import { test } from 'node:test';
import assert from 'node:assert/strict';
import { squarify, persistentSignal, holderGrowth, breadth, coreIndex, pctChange,
  lrets, pcorr, betaVs, corrColor, winRet, rsComposite,
  laggedCorr, dstats, rsi, rsiArr, rsiDiv, ema, macdArr, macdHist,
  median, washVerdict, absorptionSignal, rugRisk } from './metrics.js';

test('rugRisk flags liquidity drain while price holds, ignores TVL that just tracks price', () => {
  const flat = [{ tvl: 100, price: 1 }, { tvl: 100, price: 1 }, { tvl: 100, price: 1 }];
  assert.equal(rugRisk([...flat, { tvl: 60, price: 0.98 }]).level, 'high');   // TVL -40%, price -2%
  assert.equal(rugRisk([...flat, { tvl: 84, price: 1.05 }]).level, 'watch');  // TVL -16%, price +5%
  assert.equal(rugRisk([...flat, { tvl: 60, price: 0.6 }]).level, 'ok');      // both -40% = TVL tracks price, not a rug
  assert.equal(rugRisk([{ tvl: 1, price: 1 }]), null);                        // too little history
});

test('squarify covers the full area', () => {
  const items = [{ value: 6 }, { value: 6 }, { value: 4 }, { value: 3 }, { value: 2 }, { value: 1 }];
  const rects = squarify(items, 600, 400);
  assert.equal(rects.length, items.length);
  const area = rects.reduce((s, r) => s + r.w * r.h, 0);
  assert.ok(Math.abs(area - 600 * 400) < 1, 'area ~= W*H');
  for (const r of rects) { assert.ok(r.w > 0 && r.h > 0); }
});

test('persistentSignal detects rug_confirmed', () => {
  const arr = [{ tvl: 100, holders: 10, price: 1 }, { tvl: 85, holders: 10, price: 1 }, { tvl: 70, holders: 10, price: 1 }];
  assert.equal(persistentSignal(arr).kind, 'rug_confirmed');
});

test('persistentSignal detects accum_confirmed', () => {
  const arr = [{ tvl: 100, holders: 100, price: 2 }, { tvl: 100, holders: 102, price: 1.9 }, { tvl: 100, holders: 104, price: 1.8 }];
  assert.equal(persistentSignal(arr).kind, 'accum_confirmed');
});

test('persistentSignal returns null below 3 snapshots', () => {
  assert.equal(persistentSignal([{ tvl: 1 }]), null);
});

test('holderGrowth computes pct and days', () => {
  const g = holderGrowth([{ holders: 100 }, { holders: 110 }, { holders: 121 }]);
  assert.equal(g.days, 2);
  assert.ok(Math.abs(g.pct - 21) < 1e-9);
});

test('breadth counts above-average CORE', () => {
  const b = breadth([
    { core: true, price: 11, avgPrice: 10 },
    { core: true, price: 9, avgPrice: 10 },
    { core: false, price: 5, avgPrice: 1 }
  ]);
  assert.equal(b.total, 2);
  assert.equal(b.above, 1);
  assert.equal(b.pct, 50);
});

test('coreIndex is mcap-weighted', () => {
  const v = coreIndex([{ core: true, d7: 10, mcap: 75 }, { core: true, d7: -10, mcap: 25 }]);
  assert.ok(Math.abs(v - 5) < 1e-9);
});

test('pctChange guards zero base', () => {
  assert.equal(pctChange(0, 5), null);
  assert.equal(pctChange(100, 110), 10);
});

import { computeMarketRegime, buildBenchmark } from './metrics.js';

const mkSnaps = (prices) => prices.map((p, i) => ({ d: '2026-06-' + (12 + i), tokens: { A: { price: p }, B: { price: p * 2 } } }));

test('computeMarketRegime BULL when all above 7d avg', () => {
  const snaps = mkSnaps([1, 1, 1, 1, 1, 1, 2]); // last well above window mean
  const r = computeMarketRegime(snaps, { A: 'meme', B: 'meme' });
  assert.equal(r.regime, 'BULL');
  assert.equal(r.total, 2);
});

test('computeMarketRegime BEAR when all below', () => {
  const snaps = mkSnaps([2, 2, 2, 2, 2, 2, 1]);
  assert.equal(computeMarketRegime(snaps, { A: 'meme', B: 'meme' }).regime, 'BEAR');
});

test('computeMarketRegime excludes stable/staking', () => {
  const r = computeMarketRegime(mkSnaps([1, 2]), { A: 'stable', B: 'staking' });
  assert.equal(r, null);
});

test('buildBenchmark starts at 1000 and tracks equal-weight', () => {
  const b = buildBenchmark(mkSnaps([1, 2]), { A: 'meme', B: 'meme' });
  assert.equal(b[0].v, 1000);
  assert.equal(b.length, 2);
});

// ---- Analytics metrics (corr / momentum) ----
test('pcorr: perfect positive = 1, anti = -1, short = null', () => {
  const a = [1, 2, 3, 4, 5], b = [2, 4, 6, 8, 10];
  assert.ok(Math.abs(pcorr(a, b) - 1) < 1e-9);
  assert.ok(Math.abs(pcorr(a, [10, 8, 6, 4, 2]) + 1) < 1e-9);
  assert.equal(pcorr([1, 2, 3], [1, 2, 3]), null); // n<5
});

test('lrets length and zero-guard', () => {
  assert.deepEqual(lrets([1, 1, 1]).map((x) => Math.round(x)), [0, 0]);
  const r = lrets([10, 20]); assert.equal(r.length, 1); assert.ok(Math.abs(r[0] - Math.log(2)) < 1e-9);
  assert.deepEqual(lrets([0, 5]), [0]); // non-positive → 0
});

test('betaVs: self = 1, 2x = 2', () => {
  const m = [0.01, -0.02, 0.03, -0.01, 0.02];
  assert.ok(Math.abs(betaVs(m, m) - 1) < 1e-9);
  assert.ok(Math.abs(betaVs(m.map((x) => 2 * x), m) - 2) < 1e-9);
  assert.equal(betaVs([1, 2, 3], [1, 2, 3]), null); // n<5
});

test('corrColor: bounds and null', () => {
  assert.equal(corrColor(null), 'transparent');
  assert.ok(corrColor(1).startsWith('rgba(46,158,91'));
  assert.ok(corrColor(-1).startsWith('rgba(207,79,95'));
});

test('winRet: percent over n closes, short = null', () => {
  assert.equal(winRet([10, 11, 12, 13, 14, 15, 16, 20], 7), 100); // first→last over 7 steps
  assert.equal(winRet([1, 2], 7), null);
  assert.equal(winRet([0, 0, 0, 0, 0, 0, 0, 5], 7), null); // zero base
});

test('rsComposite: best window → top percentile', () => {
  const rs = rsComposite([[10], [20], [30]]); // three tokens, one window
  assert.equal(rs[2], 100); // highest return = 100th pct
  assert.equal(rs[0], 0);
});

// ---- Lead-lag / risk-return / RSI / MACD ----
test('laggedCorr finds lead-1', () => {
  const a = [1, 2, 3, 4, 5, 6], b = [0, 1, 2, 3, 4, 5]; // b[t+1] == a[t]
  assert.ok(Math.abs(laggedCorr(a, b, 1) - 1) < 1e-9);
});

test('dstats mean/std', () => {
  const s = dstats([1, 2, 3, 4, 5]);
  assert.equal(s.mean, 3); assert.ok(Math.abs(s.std - Math.sqrt(2)) < 1e-9);
  assert.equal(dstats([1]), null);
});

test('rsi all-up = 100, short = null', () => {
  const up = Array.from({ length: 16 }, (_, i) => i + 1);
  assert.equal(rsi(up, 14), 100);
  assert.equal(rsi([1, 2, 3], 14), null);
});

test('rsiArr defines value at n, null before', () => {
  const up = Array.from({ length: 20 }, (_, i) => i + 1);
  const o = rsiArr(up, 14); assert.ok(o.r[14] != null); assert.equal(o.r[13], null);
});

test('rsiDiv null when too short', () => {
  assert.equal(rsiDiv([1, 2, 3, 4, 5], 14, 5), null);
  const seq = Array.from({ length: 30 }, (_, i) => 10 + Math.sin(i));
  const d = rsiDiv(seq, 14, 5); assert.ok(d === null || typeof d === 'object');
});

test('ema flat series stays flat', () => {
  assert.deepEqual(ema([5, 5, 5], 2), [5, 5, 5]);
});

test('macdArr null<35, defined>=35; macdHist finite', () => {
  assert.equal(macdArr(Array.from({ length: 30 }, (_, i) => i + 1)), null);
  const s = Array.from({ length: 40 }, (_, i) => 100 + i);
  const o = macdArr(s); assert.ok(o && o.h.length === 40);
  const m = macdHist(s); assert.ok(Number.isFinite(m.h) && typeof m.cross === 'boolean');
});

// ---- Microstructure / valuation ----
test('median odd/even/empty/nulls', () => {
  assert.equal(median([3, 1, 2]), 2);
  assert.equal(median([1, 2, 3, 4]), 2.5);
  assert.equal(median([]), null);
  assert.equal(median([null, 5, null]), 5);
});

test('washVerdict thresholds', () => {
  assert.equal(washVerdict(1), 'ok');
  assert.equal(washVerdict(3), 'elevated');
  assert.equal(washVerdict(4.9), 'elevated');
  assert.equal(washVerdict(5), 'wash');
});

test('absorptionSignal cases', () => {
  assert.equal(absorptionSignal(5, 5, 0), null);             // <20 txns
  assert.equal(absorptionSignal(80, 20, -2), 'sell_wall');   // buys-heavy, price down
  assert.equal(absorptionSignal(20, 80, 2), 'accumulation'); // sells-heavy, price up
  assert.equal(absorptionSignal(50, 50, 5), null);           // balanced
  assert.equal(absorptionSignal(80, 20, 10), null);          // buys-heavy but price ripping
});
