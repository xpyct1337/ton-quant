// Pure analytics ported from the vanilla index.html (squarify, persistentSignal,
// holderGrowth) plus small helpers. No DOM, no fetch — unit-testable.

export const pctChange = (a, b) => (a > 0 && b != null ? (b - a) / a * 100 : null);

// Treemap color: green for up, red for down, gray near-flat. Ported from tmColor.
export function tmColor(d) {
  if (!isFinite(d)) return '#7c8497';
  if (Math.abs(d) < 0.15) return '#7c8497';
  const x = Math.max(-10, Math.min(10, d)) / 10;
  return x >= 0
    ? `rgb(${Math.round(24 + (1 - x) * 60)},${Math.round(140 + x * 45)},${Math.round(87 + (1 - x) * 30)})`
    : `rgb(${Math.round(180 + -x * 35)},${Math.round(80 - -x * 25)},${Math.round(70 - -x * 15)})`;
}

// Squarified treemap (Bruls et al.). Ported verbatim from index.html.
export function squarify(items, W, H) {
  const total = items.reduce((s, i) => s + i.value, 0);
  if (total <= 0) return [];
  const sc = items.map((i) => ({ it: i, area: (i.value / total) * W * H }));
  let rects = [], x = 0, y = 0, w = W, h = H, row = [];
  const worst = (row, len) => {
    const s = row.reduce((a, b) => a + b.area, 0);
    let mx = 0;
    for (const r of row) {
      const ratio = Math.max((len * len * r.area) / (s * s), (s * s) / (len * len * r.area));
      mx = Math.max(mx, ratio);
    }
    return mx;
  };
  const layout = (row) => {
    const s = row.reduce((a, b) => a + b.area, 0);
    if (w >= h) {
      const rw = s / h; let yy = y;
      for (const r of row) { const rh = r.area / rw; rects.push({ it: r.it, x, y: yy, w: rw, h: rh }); yy += rh; }
      x += rw; w -= rw;
    } else {
      const rh = s / w; let xx = x;
      for (const r of row) { const rw2 = r.area / rh; rects.push({ it: r.it, x: xx, y, w: rw2, h: rh }); xx += rw2; }
      y += rh; h -= rh;
    }
  };
  for (const it of sc) {
    const len = Math.min(w, h);
    if (!row.length || worst([...row, it], len) <= worst(row, len)) row.push(it);
    else { layout(row); row = [it]; }
  }
  if (row.length) layout(row);
  return rects;
}

// Persistent (multi-snapshot) signal. Ported from index.html.
export function persistentSignal(arr) {
  if (!arr || arr.length < 3) return null;
  const n = arr.length, s0 = arr[n - 3], s1 = arr[n - 2], s2 = arr[n - 1];
  const tvl0 = s0.tvl || 0, tvl1 = s1.tvl || 0, tvl2 = s2.tvl || 0;
  const tvlD1 = tvl0 > 0 ? (tvl1 - tvl0) / tvl0 * 100 : null;
  const tvlD2 = tvl1 > 0 ? (tvl2 - tvl1) / tvl1 * 100 : null;
  const tvlTot = tvl0 > 0 ? (tvl2 - tvl0) / tvl0 * 100 : null;
  if (tvlD1 !== null && tvlD2 !== null && tvlD1 < -10 && tvlD2 < -10 && tvlTot < -20)
    return { kind: 'rug_confirmed', dtvl: tvlTot, d1: tvlD1, d2: tvlD2 };
  const h0 = Math.max(s0.holders || 1, 1), h1 = Math.max(s1.holders || 1, 1), h2 = Math.max(s2.holders || 1, 1);
  const hD1 = (h1 - h0) / h0 * 100, hD2 = (h2 - h1) / h1 * 100, hTot = (h2 - h0) / h0 * 100;
  if (hD1 < -0.5 && hD2 < -0.5 && hTot < -1) return { kind: 'holder_exodus', dh: hTot, d1: hD1, d2: hD2 };
  const p0 = s0.price || 0, p1 = s1.price || 0, p2 = s2.price || 0;
  const pD1 = p0 > 0 ? (p1 - p0) / p0 * 100 : null, pD2 = p1 > 0 ? (p2 - p1) / p1 * 100 : null;
  if (hD1 > 0.5 && hD2 > 0.5 && pD1 !== null && pD1 < 0 && pD2 !== null && pD2 < 0)
    return { kind: 'accum_confirmed', dh: hTot };
  return null;
}

// Holder growth over the snapshot window. Ported from index.html.
export function holderGrowth(arr) {
  if (!arr || arr.length < 2) return null;
  const h0 = Number(arr[0] && arr[0].holders) || 0;
  const h1 = Number(arr[arr.length - 1] && arr[arr.length - 1].holders) || 0;
  if (h0 <= 0 || h1 <= 0) return null;
  return { pct: (h1 - h0) / h0 * 100, days: arr.length - 1, from: h0, to: h1 };
}

// Breadth: share of CORE tokens above their own window-average price.
export function breadth(rows) {
  const core = rows.filter((r) => r.core && r.avgPrice > 0 && r.price > 0);
  if (!core.length) return null;
  const above = core.filter((r) => r.price >= r.avgPrice).length;
  return { above, total: core.length, pct: (above / core.length) * 100 };
}

// Mcap-weighted index 7d % across CORE basket.
export function coreIndex(rows) {
  const core = rows.filter((r) => r.core && r.d7 != null && r.mcap > 0);
  const tot = core.reduce((s, r) => s + r.mcap, 0);
  if (tot <= 0) return null;
  return core.reduce((s, r) => s + (r.mcap / tot) * r.d7, 0);
}

// Market regime from a 7-day snapshot window. Ported from paper.html.
// snaps = [{ d, tokens:{ addr:{price} } }] oldest→newest; cats = { addr: category }.
export function computeMarketRegime(snaps, cats) {
  if (!snaps || snaps.length < 2) return null;
  const coreA = Object.entries(cats || {}).filter(([, c]) => c !== 'stable' && c !== 'staking').map(([a]) => a);
  if (!coreA.length) return null;
  const now = snaps[snaps.length - 1].tokens || {};
  const window7 = snaps.slice(-7);
  let above = 0, total = 0;
  for (const a of coreA) {
    const pp = window7.map((s) => (s.tokens?.[a] || {}).price).filter(Boolean);
    const avg = pp.length ? pp.reduce((s, p) => s + p, 0) / pp.length : null;
    const cur = (now[a] || {}).price;
    if (cur && avg) { total++; if (cur > avg) above++; }
  }
  if (!total) return null;
  const breadth = Math.round((above / total) * 100);
  const regime = breadth >= 60 ? 'BULL' : breadth <= 40 ? 'BEAR' : 'NEUTRAL';
  const snap7 = snaps.length >= 7 ? snaps[snaps.length - 7] : snaps[0];
  const chg = coreA.map((a) => {
    const p0 = (snap7.tokens?.[a] || {}).price, p1 = (now[a] || {}).price;
    return p0 && p1 ? (p1 / p0 - 1) * 100 : null;
  }).filter((v) => v !== null).sort((a, b) => a - b);
  const med7 = chg.length ? chg[Math.floor(chg.length / 2)] : null;
  return { regime, breadth, above, total, med7 };
}

// Equal-weight CORE buy&hold from $1000 at snaps[0]. Ported from paper.html.
export function buildBenchmark(snaps, cats) {
  if (!snaps || snaps.length < 2) return null;
  const coreA = Object.entries(cats || {}).filter(([, c]) => c !== 'stable' && c !== 'staking').map(([a]) => a);
  const base0 = {};
  for (const a of coreA) { const t = snaps[0].tokens?.[a]; if (t && t.price > 0) base0[a] = t.price; }
  const eligible = Object.keys(base0);
  if (!eligible.length) return null;
  return snaps.map(({ d, tokens }) => {
    const rets = eligible.map((a) => { const t = tokens?.[a]; return t && t.price > 0 ? t.price / base0[a] : 1; });
    const mean = rets.reduce((s, r) => s + r, 0) / rets.length;
    return { d, v: Math.round(1000 * mean * 100) / 100 };
  });
}
