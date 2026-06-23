<script>
  // SVG price line + trailing cost-basis (avg) overlay + area. points=[{d,v}]
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
</script>

<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="pc" role="img" aria-label="Price vs cost-basis">
  <path d={area} fill={up ? 'rgba(22,199,132,.10)' : 'rgba(246,70,93,.10)'} />
  <line x1={pad} y1={avgY} x2={W - pad} y2={avgY} stroke="#8b94a7" stroke-dasharray="5 5" stroke-width="1" />
  <path d={line} fill="none" stroke={up ? '#16c784' : '#f6465d'} stroke-width="2" />
</svg>
<div class="cap muted">─ цена · ┄ средняя себестоимость (proxy)</div>

<style>.pc{width:100%;height:200px;display:block}.cap{font-size:11px;margin-top:6px}</style>
