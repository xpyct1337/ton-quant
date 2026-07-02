// Cross-DEX arbitrage math. Pure — unit-tested in arb.test.js.
// Port of the netArb reference from unit.test.mjs (ex-screener.html).

// Usable pool views for one jetton from a DexScreener pairs payload.
export function poolViews(pairs, addr, minLiq = 1000) {
  return (pairs || [])
    .filter((p) => p.chainId === 'ton' && p.baseToken?.address === addr &&
      (p.liquidity?.usd || 0) >= minLiq && parseFloat(p.priceUsd) > 0)
    .map((p) => ({
      dex: p.dexId || 'dex', pair: `${p.baseToken?.symbol}/${p.quoteToken?.symbol}`,
      price: parseFloat(p.priceUsd), liq: p.liquidity?.usd || 0, vol: p.volume?.h24 || 0,
      url: p.url || null
    }))
    .sort((a, b) => b.liq - a.liq);
}

// Widest buy-low/sell-high pool pair. null when fewer than 2 pools.
export function grossSpread(pools) {
  if (!pools || pools.length < 2) return null;
  let buy = pools[0], sell = pools[0];
  for (const p of pools) { if (p.price < buy.price) buy = p; if (p.price > sell.price) sell = p; }
  if (buy === sell || buy.price <= 0) return null;
  return { buy, sell, pct: (sell.price - buy.price) / buy.price * 100 };
}

// Realizable net arb after costs: scan trade sizes, model CPMM slippage on both
// legs (s/y per leg), DEX fees on both swaps, flat gas. cap = 50% of the thinner
// half-reserve so the model stays in its linear-ish regime.
export function netArb(spreadFrac, cheapLiq, expLiq, { fees = 0.006, gasUsd = 0.15 } = {}) {
  const yc = cheapLiq / 2, ye = expLiq / 2, cap = Math.min(yc, ye) * 0.5;
  let best = { netUsd: -Infinity, netPct: 0, size: 0 };
  for (let s = 20; s <= cap; s *= 1.4) {
    const slip = s / yc + s / ye;
    const netUsd = s * (spreadFrac - slip - fees) - gasUsd;
    if (netUsd > best.netUsd) best = { netUsd, netPct: (spreadFrac - slip - fees - gasUsd / s) * 100, size: s };
  }
  if (best.size === 0) best = { netUsd: -gasUsd, netPct: (spreadFrac - fees) * 100, size: 0 };
  return best;
}

// Full per-token arb view from a DexScreener payload. null if <2 usable pools.
export function arbView(pairs, addr) {
  const pools = poolViews(pairs, addr);
  const g = grossSpread(pools);
  if (!g) return null;
  const net = netArb(g.pct / 100, g.buy.liq, g.sell.liq);
  return { pools, ...g, net };
}
