<script>
  import { median } from '$lib/metrics.js';
  import { fmtUsd } from '$lib/format.js';
  let { rows = [] } = $props();

  let model = $derived.by(() => {
    const base = rows.filter((r) => r.core && r.mcap > 0 && r.holders > 0)
      .map((r) => ({ sym: r.sym, mcap: r.mcap, holders: r.holders, ph: r.mcap / r.holders }));
    if (base.length < 3) return null;
    const med = median(base.map((r) => r.ph));
    base.forEach((r) => (r.rel = med ? r.ph / med : 1));
    base.sort((a, b) => b.ph - a.ph);
    return { rows: base, med };
  });
</script>

{#if !model}
  <div class="empty">Недостаточно токенов с холдерами.</div>
{:else}
  <div class="wrap">
    <table class="ph">
      <thead><tr><th></th><th class="r">mcap</th><th class="r">холдеры</th><th class="r">$/холдер</th><th class="r">vs медиана</th></tr></thead>
      <tbody>
        {#each model.rows as r}
          <tr>
            <th class="rh">{r.sym}</th>
            <td class="r m">{fmtUsd(r.mcap)}</td>
            <td class="r m">{r.holders.toLocaleString('ru')}</td>
            <td class="r v">{fmtUsd(r.ph)}</td>
            <td class="r rel" class:hi={r.rel >= 2} class:lo={r.rel <= 0.5}>{r.rel.toFixed(1)}×</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <div class="note">$/холдер = mcap на одного держателя. Медиана набора: <strong>{fmtUsd(model.med)}</strong>. Высоко над медианой = капитализацию держит мало кошельков (раздут или концентрирован); сильно ниже = размазан по толпе. Кросс-скрининг переоценки, судить тебе.</div>
{/if}

<style>
  .wrap{overflow-x:auto}
  .ph{width:100%;border-collapse:collapse;font-size:12px}
  .ph th{color:var(--dim);font-weight:400;padding:4px 8px;font-size:11px;text-align:left}
  .ph .r{text-align:right;font-family:var(--mono)}
  .ph td{padding:6px 8px;border-top:1px solid var(--border)}
  .ph .rh{text-align:left;color:var(--text);font-weight:500}
  .ph .m{color:var(--muted)} .ph .v{color:var(--text)}
  .rel{color:var(--muted)} .rel.hi{color:#e0a93a;font-weight:600} .rel.lo{color:#5aa9c9}
  .note{font-size:12px;color:var(--muted);margin-top:10px;line-height:1.5}
  .note strong{color:var(--text)}
  .empty{color:var(--muted);font-size:13px;padding:24px 4px}
</style>
