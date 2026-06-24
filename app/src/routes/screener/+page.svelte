<script>
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { loadUniverse } from '$lib/data.js';
  import { fmtUsd, fmtPct } from '$lib/format.js';

  let st = $state('loading');
  let toks = $state([]);
  let updated = $state('');
  let cat = $state('all');
  let sort = $state('vol24');
  let q = $state('');

  const cats = [['all', 'Все'], ['meme', 'Memes'], ['defi', 'DeFi'], ['stable', 'Stables'], ['staking', 'Staking']];
  const sorts = [['vol24', 'Vol 24h'], ['mcap', 'MCap'], ['liq', 'Liquidity'], ['d1', '24h %']];

  let view = $derived(
    toks.filter((t) => (cat === 'all' || t.cat === cat) &&
        (!q || t.sym.toLowerCase().includes(q.toLowerCase()) || t.addr.toLowerCase().includes(q.toLowerCase())))
      .sort((a, b) => (b[sort] ?? -Infinity) - (a[sort] ?? -Infinity))
  );

  onMount(async () => {
    const u = await loadUniverse();
    toks = u.tokens || []; updated = u.updated || '';
    st = toks.length ? 'ready' : 'empty';
  });
</script>

<svelte:head><title>Screener — TON Quant</title></svelte:head>

<header class="hd">
  <div class="hd-top"><h1>Screener</h1><span class="muted">вся ликвидная TON-вселенная · авто-дискавери</span>{#if updated}<span class="muted upd">обновлено {updated}</span>{/if}</div>
  <div class="tabs">{#each cats as [id, label]}<button class="tab" class:on={cat === id} onclick={() => (cat = id)}>{label}</button>{/each}</div>
</header>

{#if st === 'loading'}<div class="muted pad">Загружаю вселенную…</div>
{:else if st === 'empty'}<div class="muted pad">universe.json пуст — запусти scripts/universe.py.</div>
{:else}
  <div class="ctrl">
    <input class="search" placeholder="Поиск по тикеру или адресу…" bind:value={q} />
    <div class="sorts">{#each sorts as [id, label]}<button class="chip" class:on={sort === id} onclick={() => (sort = id)}>{label}</button>{/each}</div>
    <span class="muted cnt">{view.length} монет</span>
  </div>
  <div class="card tw">
    <table>
      <thead><tr><th>Jetton</th><th>Кат.</th><th class="r">Price</th><th class="r">24h</th><th class="r">MCap</th><th class="r">Liquidity</th><th class="r">Vol 24h</th></tr></thead>
      <tbody>
        {#each view as t}
          <tr>
            <td data-label="Jetton"><a href="{base}/token?a={t.addr}"><span class="sym">{t.sym}</span></a></td>
            <td data-label="Кат." class="muted">{t.cat}</td>
            <td data-label="Price" class="r mono">{fmtUsd(t.price)}</td>
            <td data-label="24h" class="r mono" class:good={t.d1 > 0} class:bad={t.d1 < 0}>{fmtPct(t.d1)}</td>
            <td data-label="MCap" class="r mono">{fmtUsd(t.mcap)}</td>
            <td data-label="Liquidity" class="r mono">{fmtUsd(t.liq)}</td>
            <td data-label="Vol 24h" class="r mono">{fmtUsd(t.vol24)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .hd{margin-bottom:16px}.hd-top{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}h1{font-size:24px}
  .upd{font-size:12px}.pad{padding:30px 0}
  .tabs{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
  .tab{background:transparent;border:none;color:var(--muted);padding:6px 2px;font-size:13px;cursor:pointer;border-bottom:2px solid transparent}
  .tab.on{color:var(--accent);border-bottom-color:var(--accent)}
  .ctrl{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
  .search{flex:1;min-width:200px;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:9px;padding:8px 12px;font-size:13px}
  .sorts{display:flex;gap:7px}.cnt{font-size:12px}
  .chip{background:transparent;border:1px solid var(--border);color:var(--muted);border-radius:8px;padding:5px 11px;font-size:12px;cursor:pointer}
  .chip.on{background:rgba(34,167,255,.13);border-color:transparent;color:var(--accent)}
  .tw{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px}
  th{color:var(--dim);font-weight:400;text-align:left;padding:7px 10px;font-size:11px;white-space:nowrap}
  td{padding:9px 10px;border-top:1px solid var(--border);white-space:nowrap}
  .r{text-align:right}.sym{font-weight:500}

  @media(max-width:640px){
    table{display:block}thead{display:none}
    tbody{display:flex;flex-direction:column;gap:8px}
    tr{display:grid;grid-template-columns:1fr 1fr;gap:3px 10px;background:var(--card2);border:1px solid var(--border);border-radius:10px;padding:9px 12px}
    td{border-top:none;padding:2px 0;text-align:left;display:flex;justify-content:space-between;gap:8px;white-space:normal}
    td::before{content:attr(data-label);color:var(--muted);font-size:11px}
    td:first-child{grid-column:1/-1}td:first-child::before{display:none}
  }
</style>
