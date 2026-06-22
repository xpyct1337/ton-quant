import { test } from 'node:test';
import assert from 'node:assert/strict';
import { squarify, persistentSignal, holderGrowth, breadth, coreIndex, pctChange } from './metrics.js';

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
  assert.equal(b[1].v, 2000); // both doubled
});
