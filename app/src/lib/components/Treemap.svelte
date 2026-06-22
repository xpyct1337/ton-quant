<script>
  import { squarify, tmColor } from '$lib/metrics.js';
  import { base } from '$app/paths';
  let { rows } = $props();
  const W = 1000, H = 380;
  let rects = $derived(
    squarify(
      rows.filter((r) => r.core && r.mcap > 0)
        .map((r) => ({ value: r.mcap, r }))
        .sort((a, b) => b.value - a.value),
      W, H
    )
  );
</script>

<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="tm" role="img" aria-label="Market map by market cap">
  {#each rects as rc}
    <a href="{base}/token.html?a={rc.it.r.addr}">
      <rect x={rc.x + 1} y={rc.y + 1} width={Math.max(rc.w - 2, 0)} height={Math.max(rc.h - 2, 0)}
        rx="4" fill={tmColor(rc.it.r.d7)} />
      {#if rc.w > 64 && rc.h > 30}
        <text x={rc.x + 8} y={rc.y + 20} class="tm-sym">{rc.it.r.sym}</text>
        <text x={rc.x + 8} y={rc.y + 36} class="tm-pct">{rc.it.r.d7 == null ? '' : (rc.it.r.d7 >= 0 ? '+' : '') + rc.it.r.d7.toFixed(1) + '%'}</text>
      {/if}
    </a>
  {/each}
</svg>

<style>
  .tm{width:100%;height:300px;display:block}
  .tm-sym{fill:#fff;font-family:var(--head);font-weight:600;font-size:13px}
  .tm-pct{fill:rgba(255,255,255,.85);font-family:var(--mono);font-size:11px}
  a:hover rect{opacity:.85}
</style>
