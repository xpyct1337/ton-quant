// Perp market math over Hyperliquid `metaAndAssetCtxs`. Pure — unit-tested in perps.test.js.
// Signals here are our own heuristics on public market data (funding / momentum / basis),
// the same inputs signal bots like @perptools_ai_bot trade on — их закрытые сигналы
// дёрнуть нельзя, публичного API у бота нет.

// Hourly funding rate → annualised percent.
export const fundingApr = (hourly) => hourly * 24 * 365 * 100;

// Rows from the two parallel arrays Hyperliquid returns: [meta, assetCtxs].
// Drops delisted markets and anything under `minVol` 24h notional.
export function perpRows(meta, ctxs, minVol = 1e6) {
  const uni = meta?.universe || [];
  const out = [];
  for (let i = 0; i < uni.length; i++) {
    const u = uni[i], c = ctxs?.[i];
    if (!c || u.isDelisted) continue;
    const mark = parseFloat(c.markPx), prev = parseFloat(c.prevDayPx);
    const vol = parseFloat(c.dayNtlVlm) || 0;
    if (!(mark > 0) || vol < minVol) continue;
    out.push({
      coin: u.name, maxLev: u.maxLeverage || null,
      mark, prev,
      chg24: prev > 0 ? (mark / prev - 1) * 100 : null,
      funding: parseFloat(c.funding) || 0,
      fundApr: fundingApr(parseFloat(c.funding) || 0),
      oiUsd: (parseFloat(c.openInterest) || 0) * mark,
      volUsd: vol,
      premium: (parseFloat(c.premium) || 0) * 100
    });
  }
  return out.sort((a, b) => b.volUsd - a.volUsd);
}

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// Composite bias score in [-100, 100] (positive = long tilt).
// 45% 24h momentum (±10% saturates), 35% contrarian funding (crowded longs pay
// positive funding → short tilt; ±60% APR saturates), 20% mark-oracle premium
// (±0.3% saturates, contrarian like funding).
export function signalScore(r) {
  const mom = clamp((r.chg24 ?? 0) / 10, -1, 1) * 45;
  const fund = clamp(-r.fundApr / 60, -1, 1) * 35;
  const prem = clamp(-(r.premium ?? 0) / 0.3, -1, 1) * 20;
  return { score: mom + fund + prem, mom, fund, prem };
}

export const signalLabel = (score) =>
  score >= 25 ? 'long' : score <= -25 ? 'short' : 'flat';

// Score every row, return strongest long / short candidates (score-sorted).
export function rankSignals(rows, n = 5) {
  const scored = rows.map((r) => ({ ...r, sig: signalScore(r) }));
  const longs = scored.filter((r) => signalLabel(r.sig.score) === 'long')
    .sort((a, b) => b.sig.score - a.sig.score).slice(0, n);
  const shorts = scored.filter((r) => signalLabel(r.sig.score) === 'short')
    .sort((a, b) => a.sig.score - b.sig.score).slice(0, n);
  return { scored, longs, shorts };
}

// Polyline points for an inline SVG sparkline. '' when under 2 points.
export function sparkPoints(closes, w = 120, h = 36, pad = 2) {
  const v = (closes || []).filter((x) => isFinite(x));
  if (v.length < 2) return '';
  const min = Math.min(...v), max = Math.max(...v), span = max - min || 1;
  return v.map((c, i) =>
    `${(pad + (i / (v.length - 1)) * (w - 2 * pad)).toFixed(1)},${(h - pad - ((c - min) / span) * (h - 2 * pad)).toFixed(1)}`
  ).join(' ');
}
