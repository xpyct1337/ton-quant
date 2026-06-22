import { pctChange, holderGrowth } from './metrics.js';

const RAW = 'https://raw.githubusercontent.com/xpyct1337/ton-quant/main/data';
const TONAPI = 'https://tonapi.io/v2';
// ponytail: key is public in client source — free tier, revocable in tonconsole if abused.
const TONAPI_KEY = 'AEUCH5S5SBNE64AAAAAMCL5S6MOL6AFR42PEXAR3OL2K2VJTQS77IQCN7I3O54EQK76ZIFA';
const STAKING = new Set(['stable', 'staking']);

const j = (url, opt) => fetch(url, opt).then((r) => { if (!r.ok) throw new Error(r.status + ' ' + url); return r.json(); });

// Load baked snapshots + signals + scores and assemble per-token rows.
export async function loadAll() {
  const [idx, cats] = await Promise.all([j(`${RAW}/index.json`), j(`${RAW}/cats.json`)]);
  const dates = idx.dates.slice(-8);
  const snaps = await Promise.all(dates.map((d) => j(`${RAW}/snapshots/${d}.json`).catch(() => null)));
  const have = dates.filter((_, i) => snaps[i]);
  const data = snaps.filter(Boolean);
  const last = data[data.length - 1];
  const prevDay = data[data.length - 2] || last;
  const weekAgo = data[0];

  const rows = Object.entries(last.tokens).map(([addr, t]) => {
    const hist = data.map((s) => s.tokens[addr]).filter(Boolean);
    const prices = hist.map((s) => s.price).filter((p) => p > 0);
    const avgPrice = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : 0;
    const cat = cats[addr] || 'meme';
    return {
      addr, sym: t.sym, cat, core: !STAKING.has(cat),
      price: t.price, mcap: t.mcap, tvl: t.tvl, vol24: t.vol24,
      holders: t.holders, buys: t.buys, sells: t.sells, pools: t.pools,
      supply: t.supply,
      volTvl: t.tvl > 0 ? t.vol24 / t.tvl : 0,
      d1: pctChange(prevDay.tokens[addr]?.price, t.price),
      d7: pctChange(weekAgo.tokens[addr]?.price, t.price),
      avgPrice, hist, growth: holderGrowth(hist)
    };
  });
  return { rows, dates: have, ton_usd: idx.ton_usd, updated: last.date, snapCount: data.length };
}

export async function loadSignals() {
  const idx = await j(`${RAW}/signals/index.json`).catch(() => null);
  const last = idx?.dates?.[idx.dates.length - 1];
  const [today, scores] = await Promise.all([
    last ? j(`${RAW}/signals/${last}.json`).catch(() => null) : null,
    j(`${RAW}/signals/scores.json`).catch(() => null)
  ]);
  return { today, scores, date: last };
}

// Optional live price overlay (one batched TONAPI call). Degrades to snapshot prices.
export async function liveRates(addrs) {
  try {
    const url = `${TONAPI}/rates?tokens=${addrs.join('%2C')}&currencies=usd`;
    const r = await j(url, { headers: { Authorization: 'Bearer ' + TONAPI_KEY } });
    const out = {};
    for (const a of addrs) {
      const p = r.rates?.[a]?.prices?.USD;
      if (p) out[a] = p;
    }
    return out;
  } catch {
    return {};
  }
}
