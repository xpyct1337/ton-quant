import { test } from 'node:test';
import assert from 'node:assert/strict';
import { squarify, persistentSignal, holderGrowth, breadth, coreIndex, pctChange,
  lrets, pcorr, betaVs, corrColor, winRet, rsComposite } from './metrics.js';

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
