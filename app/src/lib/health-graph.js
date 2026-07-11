// Collector dependency graph for the /health page. Pure — no DOM, no fetch —
// so the layout is unit-testable and prerender-safe. Nodes are the data sources
// tracked by scripts/health.py (data/health.json). Edges are the pipeline
// dependencies (implied by the collectors, not present in health.json), authored
// here. Layout is a deterministic layered DAG (no physics), rendered as inline
// SVG by DependencyGraph.svelte — the project has no viz library by design.

// key -> Russian label. Mirrors the healthName map used on /brief.
export const NODES = {
  snapshot: 'Дневной срез',
  intraday: 'Intraday',
  wallets: 'Кошельки',
  flows: 'Потоки',
  social: 'Соцсети',
  forensics: 'Форензика',
  signals: 'Сигналы',
  xs_forward: 'XS-momentum',
  xs_audit: 'XS-audit',
  perp_markets: 'Перп-рынки',
  perp_signals: 'TG perps',
  dex_signals: 'DEX TG',
  desk: 'AI Desk'
};

// [from, to] — "to" is derived from "from". Roots (raw collectors / external TG
// parses) have no incoming edge; leaves (perp/dex TG feeds) are independent inputs.
export const EDGES = [
  ['snapshot', 'intraday'],
  ['snapshot', 'signals'],
  ['snapshot', 'flows'],
  ['snapshot', 'social'],
  ['snapshot', 'forensics'],
  ['snapshot', 'xs_forward'],
  ['xs_forward', 'xs_audit'],
  ['wallets', 'desk'],
  ['signals', 'desk'],
  ['flows', 'desk'],
  ['forensics', 'desk']
];

// Recompute freshness client-side against updated_at, the same way /brief does —
// the baked status can go stale between the snapshot run and the page view.
// Returns 'ok' | 'stale' | 'missing' | 'error' | 'unknown'.
export function nodeStatus(src, now = Date.now()) {
  if (!src) return 'unknown';
  if (src.status === 'error') return 'error';
  if (src.status === 'missing') return 'missing';
  const age = src.updated_at ? (now - new Date(src.updated_at).getTime()) / 3600000 : Infinity;
  return age > (src.max_age_h ?? Infinity) ? 'stale' : 'ok';
}

// Deterministic layered layout. Column = longest-path depth from a root; nodes at
// the same depth are spread evenly down that column. Small DAG, so a fixed-point
// relaxation over the edges is plenty. Returns { nodes:[{key,x,y}], links:[{from,to,x1,y1,x2,y2}] }.
export function layout(keys, edges, W, H, padX = 96, padY = 44) {
  const depth = Object.fromEntries(keys.map((k) => [k, 0]));
  const present = new Set(keys);
  const live = edges.filter(([a, b]) => present.has(a) && present.has(b));
  for (let changed = true; changed; ) {
    changed = false;
    for (const [a, b] of live) {
      if (depth[b] < depth[a] + 1) { depth[b] = depth[a] + 1; changed = true; }
    }
  }
  const maxD = keys.reduce((m, k) => Math.max(m, depth[k]), 0);
  const cols = {};
  for (const k of keys) (cols[depth[k]] ||= []).push(k);
  const colW = maxD > 0 ? (W - 2 * padX) / maxD : 0;
  const pos = {};
  for (let d = 0; d <= maxD; d++) {
    const col = cols[d] || [];
    const x = maxD > 0 ? padX + d * colW : W / 2;
    const step = (H - 2 * padY) / col.length;
    col.forEach((k, i) => { pos[k] = { key: k, x, y: padY + step * (i + 0.5) }; });
  }
  const nodes = keys.map((k) => pos[k]);
  const links = live.map(([a, b]) => ({ from: a, to: b, x1: pos[a].x, y1: pos[a].y, x2: pos[b].x, y2: pos[b].y }));
  return { nodes, links };
}
