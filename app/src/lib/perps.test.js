import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fundingApr, perpRows, signalScore, signalLabel, rankSignals, sparkPoints } from './perps.js';

const ctx = (mark, prev, funding = 0, oi = 0, vol = 5e6, premium = 0) => ({
  markPx: String(mark), prevDayPx: String(prev), funding: String(funding),
  openInterest: String(oi), dayNtlVlm: String(vol), premium: String(premium)
});

test('fundingApr annualises hourly rate', () => {
  assert.equal(fundingApr(0.0000125).toFixed(2), '10.95'); // 1.25bp/h ≈ 10.95% APR
  assert.equal(fundingApr(0), 0);
});

test('perpRows joins meta+ctxs, filters delisted/thin, sorts by volume', () => {
  const meta = { universe: [
    { name: 'BTC', maxLeverage: 40 }, { name: 'TON', maxLeverage: 10 },
    { name: 'DEAD', isDelisted: true }, { name: 'THIN' }
  ] };
  const ctxs = [ctx(100000, 98000, 0.0000125, 100, 9e8), ctx(2, 2.2, -0.0001, 1e6, 5e6),
    ctx(1, 1), ctx(1, 1, 0, 0, 1000)];
  const rows = perpRows(meta, ctxs);
  assert.deepEqual(rows.map((r) => r.coin), ['BTC', 'TON']);
  assert.equal(rows[0].chg24.toFixed(2), '2.04');
  assert.equal(rows[1].oiUsd, 2e6);
  assert.ok(rows[1].fundApr < -80); // -1bp/h is deeply negative annualised
});

test('signalScore: momentum long, crowded funding pushes short, bounded', () => {
  const base = { chg24: 0, fundApr: 0, premium: 0 };
  assert.equal(signalScore(base).score, 0);
  assert.ok(signalScore({ ...base, chg24: 8 }).score > 25);          // momentum → long
  assert.ok(signalScore({ ...base, fundApr: 120 }).score < -25);     // longs overpay → short
  const max = signalScore({ chg24: 99, fundApr: -999, premium: -9 }).score;
  assert.equal(max, 100); // saturates at ±100
  assert.equal(signalScore({ chg24: -99, fundApr: 999, premium: 9 }).score, -100);
});

test('signalLabel thresholds at ±25', () => {
  assert.equal(signalLabel(30), 'long');
  assert.equal(signalLabel(-30), 'short');
  assert.equal(signalLabel(10), 'flat');
});

test('rankSignals splits and orders by strength', () => {
  const rows = [
    { coin: 'UP', chg24: 9, fundApr: -30, premium: -0.1, volUsd: 1 },
    { coin: 'UP2', chg24: 6, fundApr: 0, premium: 0, volUsd: 1 },
    { coin: 'DN', chg24: -9, fundApr: 90, premium: 0.2, volUsd: 1 },
    { coin: 'MEH', chg24: 1, fundApr: 5, premium: 0, volUsd: 1 }
  ];
  const { longs, shorts, scored } = rankSignals(rows, 2);
  assert.equal(scored.length, 4);
  assert.deepEqual(longs.map((r) => r.coin), ['UP', 'UP2']);
  assert.deepEqual(shorts.map((r) => r.coin), ['DN']);
});

test('sparkPoints scales into the viewbox, empty under 2 points', () => {
  assert.equal(sparkPoints([1]), '');
  const pts = sparkPoints([1, 2, 3], 100, 30).split(' ');
  assert.equal(pts.length, 3);
  assert.equal(pts[0], '2.0,28.0');   // first = min → bottom-left
  assert.equal(pts[2], '98.0,2.0');   // last = max → top-right
});
