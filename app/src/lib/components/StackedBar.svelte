<script>
  let { buckets } = $props();
  const C = { mega: '#f6465d', whale: '#f0997b', dolphin: '#22a7ff', fish: '#16c784', shrimp: '#5b6573' };
</script>
<div class="bar">
  {#each buckets as b}{#if b.pct > 0.2}<div style="width:{b.pct}%;background:{C[b.key]}" title="{b.label}: {b.pct.toFixed(1)}%"></div>{/if}{/each}
</div>
<div class="leg">
  {#each buckets as b}
    <span class="li"><span class="dot" style="background:{C[b.key]}"></span>{b.icon} {b.label} <span class="muted">{b.count} · {b.pct.toFixed(0)}%</span></span>
  {/each}
</div>
<style>
  .bar{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--card2);margin-bottom:10px}
  .bar>div{height:100%}
  .leg{display:flex;flex-wrap:wrap;gap:12px;font-size:12px}
  .li{display:flex;align-items:center;gap:5px}
  .dot{width:8px;height:8px;border-radius:50%;display:inline-block}
</style>
