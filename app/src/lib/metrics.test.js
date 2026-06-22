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
