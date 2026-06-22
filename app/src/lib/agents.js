import { persistentSignal } from './metrics.js';

const ago = (date) => {
  const d = Math.round((Date.now() - new Date(date + 'T03:10:00Z').getTime()) / 86400000);
  return d <= 0 ? 'today' : d === 1 ? '1d ago' : d + 'd ago';
};

// Build rule-based "agent" briefing cards from data we already compute.
export function buildAgents({ rows, signals }) {
  const cards = [];
  const byAddr = Object.fromEntries(rows.map((r) => [r.addr, r]));

  // 1. Anomaly / rug-watch — persistent multi-snapshot signals.
  for (const r of rows) {
    const ps = persistentSignal(r.hist);
    if (!ps) continue;
    if (ps.kind === 'rug_confirmed')
      cards.push({ agent: 'Anomaly', icon: 'ti-radar', tone: 'bad', sym: r.sym, addr: r.addr,
        text: `${r.sym}: TVL ${ps.dtvl.toFixed(1)}% за 2 дня — подтверждённый отток ликвидности (rug-watch).` });
    else if (ps.kind === 'holder_exodus')
      cards.push({ agent: 'Anomaly', icon: 'ti-radar', tone: 'bad', sym: r.sym, addr: r.addr,
        text: `${r.sym}: холдеры ${ps.dh.toFixed(1)}% за 2 дня — исход держателей.` });
    else if (ps.kind === 'accum_confirmed')
      cards.push({ agent: 'Accumulation', icon: 'ti-trending-up', tone: 'good', sym: r.sym, addr: r.addr,
        text: `${r.sym}: холдеры растут (+${ps.dh.toFixed(1)}%) при падающей цене — тихое накопление.` });
  }

  // 2. Today's alpha signals → cards, annotated with score verdict.
  const verdict = (sig) => signals?.scores?.per_sig?.[sig]?.verdict;
  const seen = new Set();
  for (const s of signals?.today?.signals || []) {
    const key = s.sig + s.addr;
    if (seen.has(key)) continue;
    seen.add(key);
    const v = verdict(s.sig);
    const tone = s.sig === 'momentum' || s.sig.includes('accum') || s.sig === 'hidden_buyer' ? 'good' : 'info';
    cards.push({ agent: 'Flow', icon: 'ti-chart-arrows', tone, sym: s.sym, addr: s.addr,
      text: `${s.sym}: ${s.sig.replace(/_/g, ' ')}${s.d1 != null ? ' ' + (s.d1 >= 0 ? '+' : '') + s.d1.toFixed(1) + '%' : ''}` +
            `${v ? ` · сигнал: ${v}` : ''}`, when: signals?.date ? ago(signals.date) : '' });
  }

  // 3. Wash suspects (vol/TVL > 3).
  for (const r of rows.filter((x) => x.volTvl > 3).slice(0, 3))
    cards.push({ agent: 'Wash', icon: 'ti-droplet-filled', tone: 'warn', sym: r.sym, addr: r.addr,
      text: `${r.sym}: vol/TVL = ${r.volTvl.toFixed(1)}× — подозрение на wash-торговлю.` });

  const rank = { bad: 0, good: 1, warn: 2, info: 3 };
  return cards.sort((a, b) => rank[a.tone] - rank[b.tone]).slice(0, 8);
}
