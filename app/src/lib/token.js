// Token page v2.0 — pure quant helpers + loader. Synthesis over raw stats.
import { persistentSignal, holderGrowth } from './metrics.js';

const TIERS = [
  { key: 'mega', label: 'Mega whale', icon: '🐋', min: 100000 },
  { key: 'whale', label: 'Whale', icon: '🐳', min: 10000 },
  { key: 'dolphin', label: 'Dolphin', icon: '🐬', min: 1000 },
  { key: 'fish', label: 'Fish', icon: '🐟', min: 100 },
  { key: 'shrimp', label: 'Shrimp', icon: '🦐', min: 0 }
];

// TON Quant Score (0-100, 7 factors). Ported from token.html.
export function tonQuantScore({ verification, adminZero, liq, top10, holders, ageDays, taxable }) {
  const f = [
    ['Verification', verification === 'whitelist' ? 20 : verification === 'blacklist' ? -60 : 0],
    ['Mint renounced', adminZero ? 15 : 0],
    ['Liquidity', liq > 100000 ? 20 : liq > 10000 ? 12 : liq > 1000 ? 5 : 0],
    ['Top-10 spread', top10 == null ? 5 : top10 < 20 ? 15 : top10 < 40 ? 10 : top10 < 60 ? 5 : 0],
    ['Holders', holders > 10000 ? 15 : holders > 1000 ? 9 : holders > 100 ? 4 : 0],
    ['Age', ageDays == null ? 3 : ageDays > 365 ? 10 : ageDays > 90 ? 6 : ageDays > 30 ? 3 : 0],
    ['No transfer tax', taxable ? 0 : 5]
  ];
  const score = Math.max(0, Math.min(100, Math.round(f.reduce((a, [, p]) => a + p, 0))));
  return { score, factors: f.map(([label, pts]) => ({ label, pts })) };
}

export const human = (raw, decimals) => Number(raw) / Math.pow(10, decimals || 9);

// Herfindahl index over a top-holders sample.
export function hhiOf(addresses, supplyRaw) {
  const sup = Number(supplyRaw);
  if (!(sup > 0) || !addresses?.length) return null;
  const hhi = addresses.reduce((s, h) => { const sh = Number(h.balance) / sup; return s + sh * sh; }, 0);
  const label = hhi < 0.01 ? ['distributed', 'good'] : hhi < 0.1 ? ['moderate', 'warn'] : ['concentrated', 'bad'];
  return { hhi, label: label[0], cls: label[1] };
}

export function topNShare(addresses, supplyRaw, n = 10) {
  const sup = Number(supplyRaw);
  if (!(sup > 0) || !addresses?.length) return null;
  return addresses.slice(0, n).reduce((s, h) => s + Number(h.balance), 0) / sup * 100;
}

// Holder cohort tiers by USD position value.
export function tiersOf(addresses, priceUsd, decimals) {
  const buckets = TIERS.map((t) => ({ ...t, count: 0, usd: 0 }));
  for (const h of addresses || []) {
    const usd = human(h.balance, decimals) * priceUsd;
    const b = buckets.find((t) => usd >= t.min);
    if (b) { b.count++; b.usd += usd; }
  }
  const totUsd = buckets.reduce((s, b) => s + b.usd, 0) || 1;
  for (const b of buckets) b.pct = b.usd / totUsd * 100;
  const top = buckets[0].pct + buckets[1].pct;
  const verdict = top >= 60 ? ['Whale-dominated', 'bad'] : top >= 35 ? ['Mixed', 'warn'] : ['Distributed', 'good'];
  return { buckets, verdict: verdict[0], cls: verdict[1], whalePct: top };
}

// CPMM price impact for a USD trade against a pool (q = half the pool's USD liquidity).
export const slippage = (liqUsd, sizeUsd) => { const q = liqUsd / 2; return q > 0 ? (Math.pow((q + sizeUsd) / q, 2) - 1) * 100 : null; };
export function maxUnder1pct(liqUsd) { const q = liqUsd / 2; return q > 0 ? q * (Math.sqrt(1.01) - 1) : 0; }

// MVRV-lite: current price vs trailing-average cost-basis proxy. >1 = market above aggregate cost.
export function mvrvLite(points) {
  const v = (points || []).map((p) => p.v ?? p[1]).filter((x) => x > 0);
  if (v.length < 3) return null;
  const cur = v[v.length - 1], avg = v.reduce((a, b) => a + b, 0) / v.length;
  return avg > 0 ? cur / avg : null;
}
// 24h change from a ts-aware chart: last point vs the point closest to 24h before
// it (chart granularity varies, so "previous point" is NOT necessarily 24h ago).
// null when the best base is under 12h old — too close to call it a daily change.
export function chartChange24(points) {
  const pts = (points || []).filter((p) => p.t > 0 && p.v > 0);
  if (pts.length < 2) return null;
  const last = pts[pts.length - 1];
  let base = null;
  for (const p of pts) {
    if (p.t >= last.t) break;
    if (!base || Math.abs(last.t - p.t - 86400) < Math.abs(last.t - base.t - 86400)) base = p;
  }
  if (!base || last.t - base.t < 43200) return null;
  return (last.v / base.v - 1) * 100;
}

// Share of the window priced below current = rough "% supply in profit".
export function inProfitPct(points) {
  const v = (points || []).map((p) => p.v ?? p[1]).filter((x) => x > 0);
  if (v.length < 3) return null;
  const cur = v[v.length - 1];
  return v.filter((x) => x < cur).length / v.length * 100;
}

// Our scored-signal track record on this token (curated only).
export function signalEdge(hist, todaySignals, scores, addr) {
  const out = [];
  const ps = persistentSignal(hist);
  if (ps) out.push({ sig: ps.kind, verdict: 'multi-day', src: 'persistent' });
  for (const s of (todaySignals || []).filter((x) => x.addr === addr)) {
    out.push({ sig: s.sig, verdict: scores?.per_sig?.[s.sig]?.verdict || 'collecting', d1: s.d1, src: 'today' });
  }
  return out;
}

// What the paper bots actually did on this token.
export function paperTrack(bots, addr) {
  let trades = [], positions = [], realized = 0;
  for (const [bot, b] of Object.entries(bots || {})) {
    for (const t of (b.trades || []).filter((t) => t.addr === addr)) { trades.push({ ...t, bot }); realized += t.pnl || 0; }
    for (const p of (b.positions || []).filter((p) => p.addr === addr)) positions.push({ ...p, bot });
  }
  const wins = trades.filter((t) => t.pnl > 0).length;
  return { trades, positions, realized, wins, losses: trades.length - wins, n: trades.length };
}

export { holderGrowth };
