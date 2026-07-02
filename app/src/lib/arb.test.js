import { test } from 'node:test';
import assert from 'node:assert/strict';
import { poolViews, grossSpread, netArb, arbView } from './arb.js';

const pair = (dex, price, liq, addr = 'A') => ({
  chainId: 'ton', dexId: dex, priceUsd: String(price),
  baseToken: { address: addr, symbol: 'T' }, quoteToken: { symbol: 'TON' },
  liquidity: { usd: liq }, volume: { h24: 100 }
});

test('poolViews filters chain/base/liquidity and sorts by liq', () => {
  const pairs = [
    pair('stonfi', 1.0, 50000), pair('dedust', 1.05, 20000),
    pair('stonfi', 9, 500),                       // below minLiq
    { ...pair('x', 1, 9e9), chainId: 'eth' },     // wrong chain
    { ...pair('x', 1, 9e9), baseToken: { address: 'B' } } // wrong base
  ];
  const v = poolViews(pairs, 'A');
  assert.equal(v.length, 2);
  assert.equal(v[0].dex, 'stonfi'); // biggest liq first
});

test('grossSpread picks cheapest buy / dearest sell', () => {
  const g = grossSpread([
    { dex: 'a', price: 1.0, liq: 1 }, { dex: 'b', price: 1.1, liq: 1 }, { dex: 'c', price: 1.04, liq: 1 }
  ]);
  assert.equal(g.buy.dex, 'a');
  assert.equal(g.sell.dex, 'b');
  assert.equal(g.pct.toFixed(1), '10.0');
  assert.equal(grossSpread([{ dex: 'a', price: 1, liq: 1 }]), null);
});

// netArb mirrors the root-level reference tests (unit.test.mjs)
test('netArb: deep 5% profitable, thin 0.3% not, monotonic in spread & depth', () => {
  const deep = netArb(0.05, 2e6, 2e6);
  assert.ok(deep.netUsd > 0 && deep.netPct > 0);
  assert.ok(netArb(0.003, 8000, 8000).netUsd <= 0);
  assert.ok(netArb(0, 1e6, 1e6).netUsd <= 0);
  assert.ok(netArb(0.08, 1e6, 1e6).netUsd > netArb(0.04, 1e6, 1e6).netUsd);
  assert.ok(netArb(0.05, 5e6, 5e6).netUsd > netArb(0.05, 5e5, 5e5).netUsd);
  assert.ok(deep.netPct < 5); // fees+gas always subtracted
  const capped = netArb(0.1, 1e5, 3e5);
  assert.ok(capped.size <= (1e5 / 2) * 0.5 + 1e-6);
});

test('arbView composes pools+spread+net; null under 2 pools', () => {
  const v = arbView([pair('stonfi', 1.0, 100000), pair('dedust', 1.03, 80000)], 'A');
  assert.equal(v.pools.length, 2);
  assert.equal(v.buy.dex, 'stonfi');
  assert.ok(v.net.netUsd !== undefined);
  assert.equal(arbView([pair('stonfi', 1.0, 100000)], 'A'), null);
});
