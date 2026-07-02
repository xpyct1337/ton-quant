<script>
  // Multi-line equity chart (SVG, no chart dep). series = [{name,color,dash,points:[{d,v}]}]
  // X is mapped over the union of all dates, so a series that started later (e.g.
  // the alt bot) stays time-aligned with the others instead of stretching to full width.
  let { series } = $props();
  const W = 1000, H = 240, padX = 12, padY = 16;
  let dates = $derived([...new Set(series.flatMap((s) => s.points.map((p) => p.d)))].sort());
  let xi = $derived(new Map(dates.map((d, i) => [d, i])));
  let all = $derived(series.flatMap((s) => s.points.map((p) => p.v)).filter(isFinite));
  let mn = $derived(Math.min(...all, 990));
  let mx = $derived(Math.max(...all, 1010));
  const X = (d) => (dates.length <= 1 ? W / 2 : padX + ((xi.get(d) ?? 0) / (dates.length - 1)) * (W - 2 * padX));
  const Y = (v) => H - padY - ((v - mn) / (mx - mn || 1)) * (H - 2 * padY);
  let baseY = $derived(Y(1000));
  const path = (pts) => pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.d).toFixed(1)},${Y(p.v).toFixed(1)}`).join(' ');
</script>

<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="eq" role="img" aria-label="Equity curves">
  <line x1="0" y1={baseY} x2={W} y2={baseY} stroke="#2a3340" stroke-dasharray="4 4" />
  {#each series as s}
    {#if s.points.length}
      <path d={path(s.points)} fill="none" stroke={s.color} stroke-width={s.dash ? 1.6 : 2.2}
        stroke-dasharray={s.dash ? '6 4' : ''} />
    {/if}
  {/each}
</svg>

<style>.eq{width:100%;height:240px;display:block}</style>
