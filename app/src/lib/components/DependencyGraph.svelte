<script>
  import { NODES, EDGES, layout } from '$lib/health-graph.js';
  // statusOf: { key -> { status, count, age_h, updated_at, max_age_h, last_error } }
  // where status is the client-recomputed 'ok'|'stale'|'missing'|'error'|'unknown'.
  let { statusOf = {} } = $props();

  const W = 1000, H = 460, BW = 138, BH = 40;
  const keys = Object.keys(NODES);
  const g = $derived(layout(keys, EDGES, W, H));
  const posOf = $derived(Object.fromEntries(g.nodes.map((n) => [n.key, n])));

  const COLOR = { ok: 'var(--good)', stale: 'var(--warn)', error: 'var(--bad)', missing: 'var(--bad)', unknown: 'var(--muted)' };
  const fill = (k) => COLOR[statusOf[k]?.status] || COLOR.unknown;

  let hover = $state(null);
  const hv = $derived(hover ? { ...posOf[hover], key: hover, ...statusOf[hover] } : null);
  const ageTxt = (a) => (a == null ? '—' : a < 1 ? `${Math.round(a * 60)} мин` : `${a.toFixed(1)} ч`);
</script>

<div class="wrap">
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="Граф зависимостей источников данных" preserveAspectRatio="xMidYMid meet">
    {#each g.links as l}
      <line x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} class="edge" />
    {/each}
    {#each g.nodes as n}
      <g class="node" onmouseenter={() => (hover = n.key)} onmouseleave={() => (hover = null)} role="presentation">
        <rect x={n.x - BW / 2} y={n.y - BH / 2} width={BW} height={BH} rx="8" fill={fill(n.key)} />
        <text x={n.x} y={n.y + 5} class="lbl">{NODES[n.key]}</text>
      </g>
    {/each}
  </svg>

  {#if hv}
    <div class="tip" style="left:{(hv.x / W) * 100}%; top:{(hv.y / H) * 100}%">
      <strong>{NODES[hv.key]}</strong>
      <div class="st {hv.status}">{hv.status}</div>
      <div class="meta">записей: {hv.count ?? '—'} · возраст: {ageTxt(hv.age_h)} / лимит {hv.max_age_h ?? '—'} ч</div>
      {#if hv.last_error}<div class="err">{hv.last_error}</div>{/if}
    </div>
  {/if}
</div>

<style>
  .wrap { position: relative; width: 100%; }
  svg { display: block; width: 100%; height: auto; }
  .edge { stroke: var(--border); stroke-width: 1.5; }
  .node { cursor: default; }
  .node:hover rect { opacity: 0.85; }
  .lbl { fill: #fff; font-family: var(--head); font-weight: 600; font-size: 14px; text-anchor: middle; pointer-events: none; }
  .tip {
    position: absolute; transform: translate(-50%, calc(-100% - 12px));
    background: var(--card); border: 1px solid var(--border); border-radius: 9px;
    padding: 8px 10px; min-width: 160px; pointer-events: none; z-index: 5;
    box-shadow: 0 6px 20px rgba(0, 0, 0, .35);
  }
  .tip strong { display: block; font-size: 13px; }
  .st { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; margin-top: 2px; }
  .st.ok { color: var(--good); }
  .st.stale { color: var(--warn); }
  .st.error, .st.missing { color: var(--bad); }
  .st.unknown { color: var(--muted); }
  .meta { color: var(--muted); font-size: 11px; margin-top: 3px; }
  .err { color: var(--bad); font-size: 11px; margin-top: 3px; word-break: break-word; }
</style>
