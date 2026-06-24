import { pctChange, holderGrowth } from './metrics.js';

const RAW = 'https://raw.githubusercontent.com/xpyct1337/ton-quant/main/data';
const TONAPI = 'https://tonapi.io/v2';
// ponytail: key is public in client source — free tier, revocable in tonconsole if abused.
const TONAPI_KEY = 'AEUCH5S5SBNE64AAAAAMCL5S6MOL6AFR42PEXAR3OL2K2VJTQS77IQCN7I3O54EQK76ZIFA';
const STAKING = new Set(['stable', 'staking']);

const j = (url, opt) => fetch(url, opt).then((r) => { if (!r.ok) throw new Error(r.status + ' ' + url); return r.json(); });

// Load baked snapshots + signals + scores and assemble per-token rows.
export async function loadAll(days = 8) {
  const [idx, cats] = await Promise.all([j(`${RAW}/index.json`), j(`${RAW}/cats.json`)]);
  const dates = idx.dates.slice(-days);
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

import { computeMarketRegime, buildBenchmark } from './metrics.js';

const RAWB = 'https://raw.githubusercontent.com/xpyct1337/ton-quant/main/data';

// Paper bots: cons/aggr (+ alt) state, plus signal scoreboard.
export async function loadPaper() {
  const [bots, alt, scores] = await Promise.all([
    j(`${RAWB}/paper/bots.json`).catch(() => null),
    j(`${RAWB}/paper/altbots.json`).catch(() => null),
    j(`${RAWB}/signals/scores.json`).catch(() => null)
  ]);
  return { bots: { ...(bots?.bots || {}), ...(alt?.bots || {}) }, scores };
}

// Regime + buy&hold benchmark over the full snapshot history.
export async function loadRegimeBench() {
  const [idx, cats] = await Promise.all([j(`${RAWB}/index.json`), j(`${RAWB}/cats.json`)]);
  const snaps = await Promise.all(
    idx.dates.map((d) => j(`${RAWB}/snapshots/${d}.json`).then((s) => ({ d, tokens: s.tokens || {} })).catch(() => ({ d, tokens: {} })))
  );
  return { regime: computeMarketRegime(snaps, cats), bench: buildBenchmark(snaps, cats) };
}

import { tonQuantScore, hhiOf, topNShare, tiersOf, mvrvLite, inProfitPct, signalEdge, paperTrack, human } from './token.js';

// Full token page payload for any jetton address.
export async function loadToken(addr) {
  const H = { Authorization: 'Bearer ' + TONAPI_KEY };
  const [info, holders, rates, chartR, dex, ston, all, paper, sig] = await Promise.all([
    j(`${TONAPI}/jettons/${addr}`, { headers: H }),
    j(`${TONAPI}/jettons/${addr}/holders?limit=100`, { headers: H }).catch(() => ({ addresses: [], total: 0 })),
    j(`${TONAPI}/rates?tokens=${addr}%2CTON&currencies=usd`, { headers: H }).catch(() => ({ rates: {} })),
    j(`${TONAPI}/rates/chart?token=${addr}&currency=usd`, { headers: H }).catch(() => ({ points: [] })),
    j(`https://api.dexscreener.com/latest/dex/tokens/${addr}`).catch(() => null),
    j(`https://api.ston.fi/v1/assets/${addr}`).catch(() => null),
    loadAll().catch(() => ({ rows: [] })),
    loadPaper().catch(() => ({ bots: {} })),
    loadSignals().catch(() => ({}))
  ]);

  const decimals = Number(info.metadata?.decimals ?? 9);
  const supplyRaw = info.total_supply || '0';
  const supply = human(supplyRaw, decimals);
  const price = rates.rates?.[addr]?.prices?.USD ?? 0;
  const tonUsd = rates.rates?.TON?.prices?.USD ?? null;
  const addrList = holders.addresses || [];
  const totalHolders = info.holders_count ?? holders.total ?? addrList.length ?? 0;

  const pairs = ((dex && dex.pairs) || []).filter((p) => p.chainId === 'ton')
    .sort((a, b) => (b.liquidity?.usd || 0) - (a.liquidity?.usd || 0));
  const liq = pairs.reduce((s, p) => s + (p.liquidity?.usd || 0), 0);
  const vol = pairs.reduce((s, p) => s + (p.volume?.h24 || 0), 0);
  const created = Math.min(...pairs.map((p) => p.pairCreatedAt || Infinity));
  const ageDays = isFinite(created) ? Math.round((Date.now() - created) / 86400000) : null;

  const tags = ston?.asset?.tags || [];
  const taxable = !!(ston?.asset?.taxable || tags.some((t) => /taxable/.test(t)));
  const lowLiq = tags.some((t) => /low_liquidity|no_liquidity|liquidity:(low|no)/.test(t));
  const adminZero = !!info.admin?.address?.replace(/^0:/, '').match(/^0+$/);
  const verification = info.verification || 'none';

  const top10 = topNShare(addrList, supplyRaw, 10);
  const chart = (chartR.points || []).map((p) => ({ d: new Date(p[0] * 1000).toISOString().slice(0, 10), v: p[1] }))
    .filter((p) => p.v > 0);

  const curatedRow = (all.rows || []).find((r) => r.addr === addr);
  const score = tonQuantScore({ verification, adminZero, liq, top10, holders: totalHolders, ageDays, taxable });

  return {
    addr, name: info.metadata?.name || addr.slice(0, 6), symbol: info.metadata?.symbol || '',
    image: info.metadata?.image, verification, taxable, lowLiq, adminZero, decimals,
    price, priceTon: price && tonUsd ? price / tonUsd : null, mcap: price * supply, supply, holders: totalHolders,
    top10, hhi: hhiOf(addrList, supplyRaw), tiers: tiersOf(addrList, price, decimals),
    holdersList: addrList.slice(0, 100), liq, vol, pairs, ageDays,
    chart, mvrv: mvrvLite(chart), inProfit: inProfitPct(chart), score,
    curated: !!curatedRow, hist: curatedRow?.hist || [], growth: curatedRow?.growth || null,
    edge: signalEdge(curatedRow?.hist || [], sig.today?.signals, sig.scores, addr),
    track: paperTrack(paper.bots, addr), tonUsd
  };
}

// Broad discovery universe (Screener firehose).
export async function loadUniverse() {
  return j(`${RAWB}/universe.json`).catch(() => ({ tokens: [] }));
}
