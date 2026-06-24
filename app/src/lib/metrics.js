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

// ---- Analytics-page metrics ported from index.html (corr / momentum). Pure, unit-tested. ----

// Log returns from a price series. Non-positive steps → 0.
export function lrets(p) {
  const r = [];
  for (let i = 1; i < p.length; i++) { const a = p[i - 1], b = p[i]; r.push(a > 0 && b > 0 ? Math.log(b / a) : 0); }
  return r;
}

// Pearson correlation. null when fewer than 5 aligned points.
export function pcorr(a, b) {
  const n = Math.min(a.length, b.length);
  if (n < 5) return null;
  let ma = 0, mb = 0;
  for (let i = 0; i < n; i++) { ma += a[i]; mb += b[i]; }
  ma /= n; mb /= n;
  let num = 0, da = 0, db = 0;
  for (let i = 0; i < n; i++) { const ea = a[i] - ma, eb = b[i] - mb; num += ea * eb; da += ea * ea; db += eb * eb; }
  return da && db ? num / Math.sqrt(da * db) : null;
}

// Beta of series a vs market m. null when fewer than 5 points.
export function betaVs(a, m) {
  const n = Math.min(a.length, m.length);
  if (n < 5) return null;
  let ma = 0, mm = 0;
  for (let i = 0; i < n; i++) { ma += a[i]; mm += m[i]; }
  ma /= n; mm /= n;
  let cov = 0, vm = 0;
  for (let i = 0; i < n; i++) { cov += (a[i] - ma) * (m[i] - mm); vm += (m[i] - mm) ** 2; }
  return vm ? cov / vm : null;
}

// Diverging heatmap color on dark bg: +1 green, 0 transparent, -1 red.
export function corrColor(v) {
  if (v == null || !isFinite(v)) return 'transparent';
  const x = Math.max(-1, Math.min(1, v)), t = Math.abs(x);
  const al = (0.1 + t * 0.55).toFixed(3);
  return x >= 0 ? `rgba(46,158,91,${al})` : `rgba(207,79,95,${al})`;
}

// Window return over last n closes, percent. null if series too short or zero.
export function winRet(s, n) {
  if (!s || s.length < n + 1) return null;
  const a = s[s.length - 1 - n], b = s[s.length - 1];
  return a > 0 && b > 0 ? (b / a - 1) * 100 : null;
}

// Composite relative-strength: mean percentile rank across windows. retArrs = [[r7,r14,r30],...].
export function rsComposite(retArrs) {
  const nWin = retArrs.length ? retArrs[0].length : 0, pct = retArrs.map(() => []);
  for (let wi = 0; wi < nWin; wi++) {
    const idx = retArrs.map((r, i) => ({ i, v: r[wi] })).filter((o) => o.v != null).sort((a, b) => a.v - b.v);
    idx.forEach((o, k) => { pct[o.i][wi] = idx.length > 1 ? k / (idx.length - 1) * 100 : 50; });
  }
  return retArrs.map((_, i) => { const p = pct[i].filter((v) => v != null); return p.length ? p.reduce((a, b) => a + b, 0) / p.length : null; });
}

// Lag-k correlation: X at day t vs Y at day t+k. X leads Y when this is strong.
export function laggedCorr(a, b, k) { return pcorr(a.slice(0, a.length - k), b.slice(k)); }

// Daily-return mean & population std (for annualized return/vol/Sharpe).
export function dstats(r) {
  const n = r.length; if (n < 2) return null;
  let m = 0; for (const x of r) m += x; m /= n;
  let v = 0; for (const x of r) v += (x - m) * (x - m); v /= n;
  return { mean: m, std: Math.sqrt(v) };
}

// Wilder RSI(n) — last value. null if fewer than n+1 positive closes.
export function rsi(s, n) {
  const a = s.filter((x) => x > 0); if (a.length < n + 1) return null;
  let g = 0, l = 0;
  for (let i = 1; i <= n; i++) { const d = a[i] - a[i - 1]; if (d >= 0) g += d; else l -= d; }
  let ag = g / n, al = l / n;
  for (let i = n + 1; i < a.length; i++) { const d = a[i] - a[i - 1]; ag = (ag * (n - 1) + (d > 0 ? d : 0)) / n; al = (al * (n - 1) + (d < 0 ? -d : 0)) / n; }
  if (al === 0) return ag === 0 ? 50 : 100;
  return 100 - 100 / (1 + ag / al);
}

// Full Wilder RSI series aligned to prices (for divergence).
export function rsiArr(s, n) {
  const a = (s || []).filter((x) => x > 0); if (a.length < n + 1) return null;
  const out = new Array(a.length).fill(null); let g = 0, l = 0;
  for (let i = 1; i <= n; i++) { const d = a[i] - a[i - 1]; if (d >= 0) g += d; else l -= d; }
  let ag = g / n, al = l / n; const rv = () => (al === 0 ? (ag === 0 ? 50 : 100) : 100 - 100 / (1 + ag / al));
  out[n] = rv();
  for (let i = n + 1; i < a.length; i++) { const d = a[i] - a[i - 1]; ag = (ag * (n - 1) + (d > 0 ? d : 0)) / n; al = (al * (n - 1) + (d < 0 ? -d : 0)) / n; out[i] = rv(); }
  return { p: a, r: out };
}

// RSI divergence over two L-bar windows. bear/bull/null.
export function rsiDiv(s, n = 14, L = 5) {
  const o = rsiArr(s, n); if (!o) return null;
  const { p, r } = o, M = p.length; if (M < n + 2 * L + 1) return null;
  const amax = (lo, hi) => { let b = lo; for (let i = lo + 1; i <= hi; i++) if (p[i] > p[b]) b = i; return b; };
  const amin = (lo, hi) => { let b = lo; for (let i = lo + 1; i <= hi; i++) if (p[i] < p[b]) b = i; return b; };
  const rH = amax(M - L, M - 1), oH = amax(M - 2 * L, M - L - 1), rL = amin(M - L, M - 1), oL = amin(M - 2 * L, M - L - 1);
  if (r[rH] == null || r[oH] == null || r[rL] == null || r[oL] == null) return { type: null };
  if (p[rH] > p[oH] && r[rH] < r[oH]) return { type: 'bear', dr: r[rH] - r[oH] };
  if (p[rL] < p[oL] && r[rL] > r[oL]) return { type: 'bull', dr: r[rL] - r[oL] };
  return { type: null };
}

// EMA series.
export function ema(a, n) { const k = 2 / (n + 1); let e = a[0]; const o = [e]; for (let i = 1; i < a.length; i++) { e = a[i] * k + e * (1 - k); o.push(e); } return o; }

// MACD(12,26,9) on a base-100 series → { p, h } (price + histogram). null if <35 closes.
export function macdArr(s) {
  const raw = (s || []).filter((x) => x > 0); if (raw.length < 35) return null;
  const a = raw.map((x) => x / raw[0] * 100);
  const f = ema(a, 12), sl = ema(a, 26), line = a.map((_, i) => f[i] - sl[i]);
  const sig = ema(line, 9), h = line.map((v, i) => v - sig[i]);
  return { p: a, h };
}
export function macdHist(s) {
  const o = macdArr(s); if (!o) return null;
  const h = o.h, n = h.length;
  return { h: h[n - 1], prev: h[n - 2], cross: (h[n - 1] > 0) !== (h[n - 2] > 0) };
}
export function macdDiv(s, L = 5) {
  const o = macdArr(s); if (!o) return null;
  const { p, h } = o, M = p.length; if (M < 2 * L) return { type: null };
  const amax = (lo, hi) => { let b = lo; for (let i = lo + 1; i <= hi; i++) if (p[i] > p[b]) b = i; return b; };
  const amin = (lo, hi) => { let b = lo; for (let i = lo + 1; i <= hi; i++) if (p[i] < p[b]) b = i; return b; };
  const rH = amax(M - L, M - 1), oH = amax(M - 2 * L, M - L - 1), rL = amin(M - L, M - 1), oL = amin(M - 2 * L, M - L - 1);
  if (p[rH] > p[oH] && h[rH] < h[oH]) return { type: 'bear', dh: h[rH] - h[oH] };
  if (p[rL] < p[oL] && h[rL] > h[oL]) return { type: 'bull', dh: h[rL] - h[oL] };
  return { type: null };
}

// ---- Microstructure / valuation (rows-only, 0 extra requests) ----

// Median of a numeric array (nulls skipped). null when empty.
export function median(a) {
  const s = a.filter((x) => x != null).sort((x, y) => x - y), n = s.length;
  if (!n) return null;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

// Wash-trading heuristic from daily turnover (vol24 / tvl). Higher = more suspect.
// Academic flag: real DEX turnover rarely sustains >3-5x/day without fake volume.
export function washVerdict(turnover) {
  return turnover >= 5 ? 'wash' : turnover >= 3 ? 'elevated' : 'ok';
}

// Volume×Price absorption from 24h buy/sell txn counts and 1d price move.
// sell_wall = heavy buying absorbed by a seller (price flat/down despite buys).
// accumulation = heavy selling absorbed by a buyer (price flat/up despite sells).
export function absorptionSignal(buys, sells, d1) {
  const t = (buys || 0) + (sells || 0);
  if (t < 20) return null; // too few trades to read
  const br = (buys || 0) / t * 100;
  if (br >= 65 && d1 != null && d1 <= 1) return 'sell_wall';
  if (br <= 35 && d1 != null && d1 >= -1) return 'accumulation';
  return null;
}
