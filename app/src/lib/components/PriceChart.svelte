<script>
  // SVG price line + trailing cost-basis (avg) overlay + area. points=[{d,v}]
  // Axis labels and the hover tooltip are HTML overlays (the SVG is stretched with
  // preserveAspectRatio=none, so in-SVG text would distort).
  let { points } = $props();
  const W = 1000, H = 220, pad = 14;
  let vals = $derived(points.map((p) => p.v).filter((x) => x > 0));
  let mn = $derived(Math.min(...vals));
  let mx = $derived(Math.max(...vals));
  let avg = $derived(vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0);
  const X = (i, n) => (n <= 1 ? W / 2 : pad + (i / (n - 1)) * (W - 2 * pad));
  const Y = (v) => H - pad - ((v - mn) / (mx - mn || 1)) * (H - 2 * pad);
  let line = $derived(points.map((p, i) => `${i ? 'L' : 'M'}${X(i, points.length).toFixed(1)},${Y(p.v).toFixed(1)}`).join(' '));
  let area = $derived(points.length ? line + ` L${X(points.length - 1, points.length).toFixed(1)},${H - pad} L${pad},${H - pad} Z` : '');
  let up = $derived(vals.length > 1 && vals[vals.length - 1] >= vals[0]);
  let avgY = $derived(Y(avg));

  // token prices span many magnitudes — show enough significant digits
  const fmt = (v) => (v == null || !isFinite(v) ? '—' : '$' + (v >= 1 ? v.toFixed(2) : v.toPrecision(4)));

  let hover = $state(null); // { i, leftPct, topPct }
  function onMove(e) {
    if (points.length < 2) return;
    const r = e.currentTarget.getBoundingClientRect();
    const frac = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    const i = Math.round(frac * (points.length - 1));
    hover = { i, leftPct: (X(i, points.length) / W) * 100, topPct: (Y(points[i].v) / H) * 100 };
  }
</script>

<div class="wrap" onpointermove={onMove} onpointerleave={() => (hover = null)}>
  <svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="pc" role="img" aria-label="Price vs cost-basis">
    <path d={area} fill={up ? 'rgba(22,199,132,.10)' : 'rgba(246,70,93,.10)'} />
    <line x1={pad} y1={avgY} x2={W - pad} y2={avgY} stroke="#8b94a7" stroke-dasharray="5 5" stroke-width="1" />
    <path d={line} fill="none" stroke={up ? '#16c784' : '#f6465d'} stroke-width="2" />
    {#if hover}
      <line x1={X(hover.i, points.length)} y1={pad} x2={X(hover.i, points.length)} y2={H - pad}
        stroke="rgba(255,255,255,.25)" stroke-width="1" />
    {/if}
  </svg>
  <span class="yl top mono">{fmt(mx)}</span>
  <span class="yl bot mono">{fmt(mn)}</span>
  {#if hover}
    <span class="dot" style="left:{hover.leftPct}%;top:{hover.topPct}%"></span>
    <div class="tip mono" class:flip={hover.leftPct > 62} style="left:{hover.leftPct}%">
      {points[hover.i].d} · {fmt(points[hover.i].v)}
    </div>
  {/if}
</div>
<div class="xlab muted mono">
  <span>{points[0]?.d}</span>
  {#if points.length > 2}<span>{points[Math.floor((points.length - 1) / 2)].d}</span>{/if}
  <span>{points[points.length - 1]?.d}</span>
</div>
<div class="cap muted">─ цена · ┄ средняя себестоимость {fmt(avg)} (proxy)</div>

<style>
  .wrap{position:relative}
  .pc{width:100%;height:200px;display:block}
  .yl{position:absolute;right:4px;font-size:10px;color:var(--muted);background:rgba(7,10,17,.55);padding:0 4px;border-radius:4px;pointer-events:none}
  .yl.top{top:2px}.yl.bot{bottom:2px}
  .dot{position:absolute;width:8px;height:8px;border-radius:50%;background:#fff;border:2px solid var(--accent);transform:translate(-50%,-50%);pointer-events:none}
  .tip{position:absolute;top:6px;transform:translateX(8px);background:var(--card2);border:1px solid var(--border);border-radius:7px;padding:4px 9px;font-size:11px;white-space:nowrap;pointer-events:none;z-index:5}
  .tip.flip{transform:translateX(calc(-100% - 8px))}
  .xlab{display:flex;justify-content:space-between;font-size:10px;margin-top:4px}
  .cap{font-size:11px;margin-top:6px}
  .mono{font-family:var(--mono)}
</style>
