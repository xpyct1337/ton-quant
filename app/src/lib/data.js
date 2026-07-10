import { pctChange, holderGrowth, isFakeCap, overlayIntraday } from './metrics.js';

const RAW = 'https://raw.githubusercontent.com/xpyct1337/ton-quant/main/data';
const TONAPI = 'https://tonapi.io/v2';
// ponytail: key is public in client source — free tier, revocable in tonconsole if abused.
const TONAPI_KEY = 'AEUCH5S5SBNE64AAAAAMCL5S6MOL6AFR42PEXAR3OL2K2VJTQS77IQCN7I3O54EQK76ZIFA';
const STAKING = new Set(['stable', 'staking']);

const j = (url, opt) => fetch(url, opt).then((r) => { if (!r.ok) throw new Error(r.status + ' ' + url); return r.json(); });

// Newest intraday slice (15:10 UTC, written by intraday.yml) that is newer than
// `after` (unix seconds). Tries the two dates it could live under; null if none.
async function latestIntraday(after) {
  const day = (off) => new Date(Date.now() - off * 86400000).toISOString().slice(0, 10);
  for (const d of [day(0), day(1)]) {
    const s = await j(`${RAW}/intraday/${d}.json`).catch(() => null);
    if (s?.ts > after) return s;
  }
  return null;
}

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
      addr, sym: t.sym, cat, core: !STAKING.has(cat) && !isFakeCap(t.mcap, t.tvl),
      price: t.price, mcap: t.mcap, tvl: t.tvl, vol24: t.vol24,
      holders: t.holders, buys: t.buys, sells: t.sells, pools: t.pools,
      supply: t.supply,
      volTvl: t.tvl > 0 ? t.vol24 / t.tvl : 0,
      d1: pctChange(prevDay.tokens[addr]?.price, t.price),
      d7: pctChange(weekAgo.tokens[addr]?.price, t.price),
      avgPrice, hist, growth: holderGrowth(hist)
    };
  });
  // fold in a newer intraday slice (halves staleness; d1/d7 re-based to real windows)
  const intra = await latestIntraday(last.ts || 0).catch(() => null);
  if (intra) overlayIntraday(rows, intra, data);
  return {
    rows, dates: have, ton_usd: last.ton_usd ?? null, updated: last.date,
    snapCount: data.length, snaps: data, curTs: intra?.ts || last.ts || null, intraday: !!intra
  };
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

const RAWB = RAW;

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
  const [info, holders, rates, chartR, dex, ston, all, paper, sig, flowsD, socialD] = await Promise.all([
    j(`${TONAPI}/jettons/${addr}`, { headers: H }),
    j(`${TONAPI}/jettons/${addr}/holders?limit=100`, { headers: H }).catch(() => ({ addresses: [], total: 0 })),
    j(`${TONAPI}/rates?tokens=${addr}%2CTON&currencies=usd`, { headers: H }).catch(() => ({ rates: {} })),
    j(`${TONAPI}/rates/chart?token=${addr}&currency=usd`, { headers: H }).catch(() => ({ points: [] })),
    j(`https://api.dexscreener.com/latest/dex/tokens/${addr}`).catch(() => null),
    j(`https://api.ston.fi/v1/assets/${addr}`).catch(() => null),
    loadAll().catch(() => ({ rows: [] })),
    loadPaper().catch(() => ({ bots: {} })),
    loadSignals().catch(() => ({})),
    j(`${RAW}/flows.json`).catch(() => null),
    j(`${RAW}/social.json`).catch(() => null)
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
  const chart = (chartR.points || []).map((p) => ({ t: p[0], d: new Date(p[0] * 1000).toISOString().slice(0, 10), v: p[1] }))
    .filter((p) => p.v > 0);

  const curatedRow = (all.rows || []).find((r) => r.addr === addr);
  const score = tonQuantScore({ verification, adminZero, liq, top10, holders: totalHolders, ageDays, taxable });

  // collector extras (Track B): pool structure from the latest curated snapshot,
  // trade flows + social mentions from the daily collector files. All optional.
  const snapT = curatedRow?.hist?.[curatedRow.hist.length - 1];
  const collect = {
    spread: snapT?.spread ?? null, topPool: snapT?.top_pool ?? null,
    flow: flowsD?.tokens?.[addr] || null, flowDate: flowsD?.date || null,
    mentions: socialD?.tokens?.[addr]?.mentions ?? null, socialDate: socialD?.date || null
  };

  return {
    addr, name: info.metadata?.name || addr.slice(0, 6), symbol: info.metadata?.symbol || '',
    image: info.metadata?.image, verification, taxable, lowLiq, adminZero, decimals,
    price, priceTon: price && tonUsd ? price / tonUsd : null, mcap: price * supply, supply, holders: totalHolders,
    top10, hhi: hhiOf(addrList, supplyRaw), tiers: tiersOf(addrList, price, decimals),
    holdersList: addrList.slice(0, 100), liq, vol, pairs, ageDays,
    chart, mvrv: mvrvLite(chart), inProfit: inProfitPct(chart), score,
    curated: !!curatedRow, hist: curatedRow?.hist || [], growth: curatedRow?.growth || null,
    edge: signalEdge(curatedRow?.hist || [], sig.today?.signals, sig.scores, addr),
    track: paperTrack(paper.bots, addr), tonUsd, collect
  };
}

// Broad discovery universe (Screener firehose).
export async function loadUniverse() {
  return j(`${RAWB}/universe.json`).catch(() => ({ tokens: [] }));
}

// Smart-money roster: wallets that are top holders across many tracked tokens.
export async function loadWallets() {
  return j(`${RAWB}/wallets.json`).catch(() => null);
}

// AI Smart-Money Desk: latest LLM verdicts (manipulation + smart-money vetting).
// Written by scripts/desk.py on the M1; absent until the desk's first run.
export async function loadDeskStatus() {
  return j(`${RAWB}/desk/verdicts.json`).catch(() => null);
}

// AI Desk self-calibration: does manip_risk predict forward underperformance?
export async function loadDeskCalibration() {
  return j(`${RAWB}/desk/calibration.json`).catch(() => null);
}

// AI Desk researcher: learned active factors + the append-only attempt history.
export async function loadDeskFactors() {
  const [active, history] = await Promise.all([
    j(`${RAWB}/desk/factors_active.json`).catch(() => []),
    j(`${RAWB}/desk/factors_history.json`).catch(() => [])
  ]);
  return { active: active || [], history: history || [] };
}

// AI Desk copy-trading proof: vetted (copy_ok) vs all-roster forward returns.
export async function loadDeskCopytrade() {
  return j(`${RAWB}/desk/copytrade.json`).catch(() => null);
}

// Collector freshness/error contract written by the daily snapshot workflow.
export async function loadHealth() {
  return j(`${RAWB}/health.json`).catch(() => null);
}

// Perp-signal collector: parsed signals from @perptools_ai_bot via Telethon.
// Written every 4h by scripts/perp_signals.py (absent until TG secrets are set).
export async function loadPerpSignals() {
  return j(`${RAWB}/perp_signals.json`).catch(() => null);
}

// XS-momentum live paper forward-test: realized track record + current open basket.
// Both files are written daily by scripts/xs_forward.py (absent until first Actions run).
export async function loadXsForward() {
  const [equity, state] = await Promise.all([
    j(`${RAWB}/xs_forward_equity.json`).catch(() => null),
    j(`${RAWB}/xs_forward_state.json`).catch(() => null)
  ]);
  return { records: equity?.records || [], state };
}

// Audit of XS paper evidence and P&L-component coverage, refreshed daily.
export async function loadXsAudit() {
  return j(`${RAWB}/xs_audit.json`).catch(() => null);
}

// Lean per-token stats for the Compare page (no holders sample / chart / curated extras).
export async function loadCompare(addr) {
  const H = { Authorization: 'Bearer ' + TONAPI_KEY };
  const [info, rates, dex] = await Promise.all([
    j(`${TONAPI}/jettons/${addr}`, { headers: H }),
    j(`${TONAPI}/rates?tokens=${addr}%2CTON&currencies=usd`, { headers: H }).catch(() => ({ rates: {} })),
    j(`https://api.dexscreener.com/latest/dex/tokens/${addr}`).catch(() => null)
  ]);
  const decimals = Number(info.metadata?.decimals ?? 9);
  const supply = human(info.total_supply || '0', decimals);
  const price = rates.rates?.[addr]?.prices?.USD ?? 0;
  const pairs = ((dex && dex.pairs) || []).filter((p) => p.chainId === 'ton');
  const liq = pairs.reduce((s, p) => s + (p.liquidity?.usd || 0), 0);
  const vol = pairs.reduce((s, p) => s + (p.volume?.h24 || 0), 0);
  const created = Math.min(...pairs.map((p) => p.pairCreatedAt || Infinity));
  const ageDays = isFinite(created) ? Math.round((Date.now() - created) / 86400000) : null;
  const verification = info.verification || 'none';
  const adminZero = !!info.admin?.address?.replace(/^0:/, '').match(/^0+$/);
  // conytail: skip STON.fi taxable lookup here (speed for N tokens) — taxable=false in score
  const score = tonQuantScore({ verification, adminZero, liq, top10: null, holders: info.holders_count || 0, ageDays, taxable: false }).score;
  return { addr, sym: info.metadata?.symbol || addr.slice(0, 6), name: info.metadata?.name, image: info.metadata?.image,
    price, mcap: price * supply, holders: info.holders_count || 0, liq, vol, ageDays, verification, adminZero, score };
}

// Wallet holdings for the Portfolio page. Spam jettons (USD value 0) filtered out.
export async function loadWallet(addr) {
  const H = { Authorization: 'Bearer ' + TONAPI_KEY };
  const [acc, jb, rates] = await Promise.all([
    j(`${TONAPI}/accounts/${addr}`, { headers: H }),
    j(`${TONAPI}/accounts/${addr}/jettons?currencies=usd`, { headers: H }).catch(() => ({ balances: [] })),
    j(`${TONAPI}/rates?tokens=TON&currencies=usd`, { headers: H }).catch(() => ({ rates: {} }))
  ]);
  const tonUsd = rates.rates?.TON?.prices?.USD ?? 0;
  const ton = Number(acc.balance || 0) / 1e9;
  const holdings = (jb.balances || []).map((b) => {
    const amount = human(b.balance, Number(b.jetton?.decimals ?? 9));
    const price = b.price?.prices?.USD || 0;
    return { sym: b.jetton?.symbol || '?', addr: b.jetton?.address, amount, price, usd: amount * price };
  }).filter((h) => h.usd > 0.01).sort((a, b) => b.usd - a.usd);
  const tonValue = ton * tonUsd;
  const total = tonValue + holdings.reduce((s, h) => s + h.usd, 0);
  return { ton, tonUsd, tonValue, holdings, total, name: acc.name || null };
}

// Recent real DEX swaps for a token's deepest pool (GeckoTerminal). Meaningful
// activity feed — conytail: TONAPI master-account events are spam, this is real trades.
export async function loadTrades(addr) {
  const gt = (u) => j(`https://api.geckoterminal.com/api/v2/networks/ton/${u}`).catch(() => null);
  const pools = await gt(`tokens/${addr}/pools`);
  const pool = pools?.data?.[0]?.attributes?.address;
  if (!pool) return [];
  const tr = await gt(`pools/${pool}/trades`);
  return (tr?.data || []).slice(0, 25).map((t) => {
    const a = t.attributes;
    return { kind: a.kind, usd: +(a.volume_in_usd || 0), ts: a.block_timestamp, from: a.tx_from_address };
  });
}
