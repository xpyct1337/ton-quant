<script>
  import { fmtUsd, fmtPct } from '$lib/format.js';
  import { base } from '$app/paths';
  let { rows } = $props();
  const filters = [
    { id: 'all', label: 'Все' },
    { id: 'movers', label: 'Movers', fn: (r) => Math.abs(r.d1 ?? 0) >= 5 },
    { id: 'wash', label: 'Wash', fn: (r) => r.volTvl > 3 },
    { id: 'liquid', label: 'Liquid', fn: (r) => r.tvl > 50000 }
  ];
  let active = $state('all');
  let expanded = $state(false);
  let filtered = $derived(
    rows.filter((r) => { const f = filters.find((x) => x.id === active); return !f?.fn || f.fn(r); })
      .sort((a, b) => b.mcap - a.mcap)
  );
  let shown = $derived(expanded ? filtered : filtered.slice(0, 10));
</script>

<div class="chips">
  {#each filters as f}
    <button class="chip" class:on={active === f.id} onclick={() => (active = f.id)}>{f.label}</button>
  {/each}
</div>

<div class="tw">
  <table>
    <thead><tr>
      <th>Jetton</th><th class="r">Price</th><th class="r">24h</th><th class="r">7d</th>
      <th class="r">MCap</th><th class="r">TVL</th><th class="r">Vol/TVL</th><th class="r">Holders 7d</th>
    </tr></thead>
    <tbody>
      {#each shown as r}
        <tr>
          <td data-label="Jetton"><a href="{base}/token?a={r.addr}"><span class="sym">{r.sym}</span> <span class="cat muted">{r.cat}</span></a></td>
          <td data-label="Price" class="r mono">{fmtUsd(r.price)}</td>
          <td data-label="24h" class="r mono" class:good={r.d1 > 0} class:bad={r.d1 < 0}>{fmtPct(r.d1)}</td>
          <td data-label="7d" class="r mono" class:good={r.d7 > 0} class:bad={r.d7 < 0}>{fmtPct(r.d7)}</td>
          <td data-label="MCap" class="r mono">{fmtUsd(r.mcap)}</td>
          <td data-label="TVL" class="r mono">{fmtUsd(r.tvl)}</td>
          <td data-label="Vol/TVL" class="r mono" class:warn={r.volTvl > 3}>{r.volTvl.toFixed(1)}×</td>
          <td data-label="Holders 7d" class="r mono" class:good={r.growth?.pct > 0.05} class:bad={r.growth?.pct < -0.05}>
            {r.growth ? (r.growth.pct >= 0 ? '▲' : '▼') + Math.abs(r.growth.pct).toFixed(1) + '%' : '—'}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
{#if filtered.length > 10}
  <button class="more" onclick={() => (expanded = !expanded)}>{expanded ? 'Свернуть' : `Показать все (${filtered.length})`}</button>
{/if}

<style>
  .chips{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
  .chip{background:transparent;border:1px solid var(--border);color:var(--muted);border-radius:8px;padding:5px 12px;font-size:12px;cursor:pointer}
  .chip.on{background:rgba(34,167,255,.13);border-color:transparent;color:var(--accent)}
  .tw{overflow-x:auto}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{color:var(--dim);font-weight:400;text-align:left;padding:7px 10px;font-size:11px;white-space:nowrap}
  td{padding:9px 10px;border-top:1px solid var(--border);white-space:nowrap}
  .r{text-align:right}
  .sym{font-weight:500}.cat{font-size:11px}
  .more{margin-top:10px;background:transparent;border:1px solid var(--border);color:var(--muted);border-radius:8px;padding:7px 14px;font-size:12px;cursor:pointer}
  .more:hover{color:var(--text)}

  @media(max-width:640px){
    table{display:block}thead{display:none}
    tbody{display:flex;flex-direction:column;gap:8px}
    tr{display:grid;grid-template-columns:1fr 1fr;gap:3px 10px;background:var(--card2);border:1px solid var(--border);border-radius:10px;padding:9px 12px}
    td{border-top:none;padding:2px 0;text-align:left;display:flex;justify-content:space-between;gap:8px;white-space:normal}
    td::before{content:attr(data-label);color:var(--muted);font-size:11px}
    td:first-child{grid-column:1/-1}td:first-child::before{display:none}
  }
</style>
