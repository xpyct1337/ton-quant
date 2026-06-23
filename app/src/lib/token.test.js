import { test } from 'node:test';
import assert from 'node:assert/strict';
import { tonQuantScore, hhiOf, topNShare, tiersOf, slippage, maxUnder1pct, mvrvLite, inProfitPct, paperTrack } from './token.js';

test('tonQuantScore clamps and sums factors', () => {
  assert.equal(tonQuantScore({ verification: 'whitelist', adminZero: true, liq: 2e5, top10: 10, holders: 2e4, ageDays: 400, taxable: false }).score, 100);
  assert.equal(tonQuantScore({ verification: 'blacklist', adminZero: false, liq: 0, top10: 90, holders: 5, ageDays: 5, taxable: true }).score, 0);
  assert.equal(tonQuantScore({ verification: 'none', adminZero: false, liq: 0, top10: null, holders: 0, ageDays: null, taxable: true }).factors.length, 7);
});

test('hhiOf classifies concentration', () => {
  const conc = hhiOf([{ balance: '60' }, { balance: '40' }], '100');
  assert.equal(conc.cls, 'bad'); // hhi=0.52 concentrated
  const dist = hhiOf(Array.from({ length: 100 }, () => ({ balance: '1' })), '100000');
  assert.equal(dist.cls, 'good');
});

test('topNShare sums top-N over supply', () => {
  assert.equal(topNShare([{ balance: '30' }, { balance: '20' }, { balance: '10' }], '100', 2), 50);
});

test('tiersOf buckets by USD and verdicts', () => {
  const r = tiersOf([{ balance: '1000000000000' }, { balance: '1000000000' }], 1, 9); // $1000 + $1
  assert.equal(r.buckets.find((b) => b.key === 'dolphin').count, 1);
  assert.ok(['Whale-dominated', 'Mixed', 'Distributed'].includes(r.verdict));
});

test('slippage rises with size, max<1% bound', () => {
  assert.ok(slippage(1e6, 100) < slippage(1e6, 10000));
  const m = maxUnder1pct(1e6);
  assert.ok(Math.abs(slippage(1e6, m) - 1) < 1e-6);
});

test('mvrvLite and inProfitPct', () => {
  const pts = [{ v: 1 }, { v: 1 }, { v: 2 }]; // avg 1.33, cur 2 -> >1
  assert.ok(mvrvLite(pts) > 1);
  assert.ok(Math.abs(inProfitPct(pts) - 200 / 3) < 1e-9); // 2 of 3 below 2
});

test('paperTrack filters by addr and tallies', () => {
  const bots = { cons: { trades: [{ addr: 'X', pnl: 5 }, { addr: 'Y', pnl: -1 }], positions: [{ addr: 'X' }] } };
  const r = paperTrack(bots, 'X');
  assert.equal(r.n, 1); assert.equal(r.wins, 1); assert.equal(r.realized, 5); assert.equal(r.positions.length, 1);
});
