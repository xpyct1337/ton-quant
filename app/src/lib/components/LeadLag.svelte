<script>
  import { lrets, laggedCorr, corrColor } from '$lib/metrics.js';
  let { rows = [] } = $props();

  let model = $derived.by(() => {
    const sel = rows.filter((r) => r.core && r.hist)
      .map((r) => ({ sym: r.sym, mcap: r.mcap || 0, spark: r.hist.map((h) => h?.price).filter((p) => p > 0) }))
      .filter((r) => r.spark.length >= 9).sort((a, b) => b.mcap - a.mcap).slice(0, 12);
    if (sel.length < 3) return null;
    const L = Math.min(...sel.map((t) => t.spark.length)); if (L < 9) return null;
    const series = sel.map((t) => lrets(t.spark.slice(-L)));
    const pairs = [], net = sel.map(() => 0);
    for (let i = 0; i < sel.length; i++) for (let j = 0; j < sel.length; j++) {
      if (i === j) continue;
      const fwd = laggedCorr(series[i], series[j], 1), rev = laggedCorr(series[j], series[i], 1);
      if (fwd == null || rev == null) continue;
      net[i] += fwd - rev;
      if (fwd >= 0.3 && fwd > rev + 0.1) pairs.push({ i, j, fwd, rev });
    }
    pairs.sort((a, b) => b.fwd - a.fwd);
    const order = sel.map((t, i) => i).sort((a, b) => net[b] - net[a]);
    return { sel, pairs: pairs.slice(0, 6), net, L, lead: order[0], follow: order[order.length - 1] };
  });
</script>

{#if !model}
  <div class="empty">Накапливаю историю — нужно ≥9 дней снапшотов.</div>
{:else}
  <div class="wrap">
    <table class="ll">
      <thead><tr><th></th><th></th><th></th><th class="r">lead r</th><th class="r">rev r</th></tr></thead>
      <tbody>
        {#if model.pairs.length}
          {#each model.pairs as p}
            <tr>
              <th class="rh">{model.sel[p.i].sym}</th><td class="m">ведёт →</td><th class="rh">{model.sel[p.j].sym}</th>
              <td class="r" style="background:{corrColor(p.fwd)}">{p.fwd.toFixed(2)}</td><td class="r m">{p.rev.toFixed(2)}</td>
            </tr>
          {/each}
        {:else}
          <tr><td colspan="5" class="m left">Нет направленного лид-лага выше порога — корзина ходит синхронно.</td></tr>
        {/if}
      </tbody>
    </table>
  </div>
  <div class="note">Сильнейший лидер: <strong>{model.sel[model.lead].sym}</strong> (net {model.net[model.lead] >= 0 ? '+' : ''}{model.net[model.lead].toFixed(1)}) — его движения опережают корзину. Главный последователь: <strong>{model.sel[model.follow].sym}</strong> (net {model.net[model.follow].toFixed(1)}). Лаг 1 день, {model.L} дней.</div>
{/if}

<style>
  .wrap{overflow-x:auto}
  .ll{border-collapse:collapse;font-size:12px}
  .ll th{color:var(--dim);font-weight:400;padding:4px 8px;font-size:11px;text-align:left}
  .ll .r{text-align:right;font-family:var(--mono)}
  .ll td{padding:5px 8px;border-top:1px solid var(--border)}
  .ll .rh{text-align:left;color:var(--text);font-weight:500;white-space:nowrap}
  .ll .m{color:var(--muted)} .ll .left{text-align:left}
  .note{font-size:12px;color:var(--muted);margin-top:10px;line-height:1.5}
  .note strong{color:var(--text)}
  .empty{color:var(--muted);font-size:13px;padding:24px 4px}
</style>
