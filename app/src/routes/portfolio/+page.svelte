<script>
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { loadWallet } from '$lib/data.js';
  import { fmtUsd, fmtNum, shortAddr } from '$lib/format.js';

  let addr = $state('');
  let w = $state(null);
  let busy = $state(false);
  let err = $state('');
  let recents = $state([]);

  const KEY = 'tq_pf_recents';
  onMount(() => { try { recents = JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { recents = []; } });
  function remember(a) {
    recents = [a, ...recents.filter((x) => x !== a)].slice(0, 6);
    try { localStorage.setItem(KEY, JSON.stringify(recents)); } catch {}
  }
  async function analyse(a = addr) {
    a = a.trim(); if (!a || busy) return;
    busy = true; err = ''; w = null;
    try { w = await loadWallet(a); addr = a; remember(a); }
    catch (e) { err = 'Не удалось: ' + e.message; }
    busy = false;
  }
</script>

<svelte:head><title>Portfolio — TON Quant</title></svelte:head>
<header class="hd"><h1>Portfolio</h1><span class="muted">холдинги любого TON-кошелька</span></header>

<div class="addbar">
  <input class="search" placeholder="Адрес кошелька (EQ… / UQ…)" bind:value={addr} onkeydown={(e) => e.key === 'Enter' && analyse()} />
  <button class="btn" onclick={() => analyse()} disabled={busy}>{busy ? '…' : 'Анализ'}</button>
</div>
{#if recents.length}<div class="recents">{#each recents as r}<button class="chip" onclick={() => analyse(r)}>{shortAddr(r)}</button>{/each}</div>{/if}
{#if err}<div class="muted err">{err}</div>{/if}

{#if w}
  <section class="kpis">
    <div class="kc"><div class="kl">Всего</div><div class="kv mono">{fmtUsd(w.total)}</div></div>
    <div class="kc"><div class="kl">TON</div><div class="kv mono">{w.ton.toFixed(2)}</div><div class="kd muted">{fmtUsd(w.tonValue)}</div></div>
    <div class="kc"><div class="kl">Жетоны (с ценой)</div><div class="kv mono">{w.holdings.length}</div></div>
  </section>
  {#if w.holdings.length}
    <div class="card tw">
      <table>
        <thead><tr><th>Жетон</th><th class="r">Кол-во</th><th class="r">Цена</th><th class="r">Стоимость</th><th class="r">Доля</th></tr></thead>
        <tbody>
          {#each w.holdings as h}
            <tr><td><a href="{base}/token?a={h.addr}" class="sym">{h.sym}</a></td>
              <td class="r mono">{fmtNum(h.amount)}</td><td class="r mono">{fmtUsd(h.price)}</td>
              <td class="r mono">{fmtUsd(h.usd)}</td><td class="r mono">{(h.usd / w.total * 100).toFixed(1)}%</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}<div class="muted pad">Жетонов с ненулевой стоимостью нет (спам-эйрдропы отфильтрованы).</div>{/if}
{:else if !busy}
  <div class="muted pad">Введи адрес кошелька — покажу TON + жетоны с реальной стоимостью.</div>
{/if}

<style>
  .hd{display:flex;align-items:baseline;gap:12px;margin-bottom:16px}h1{font-size:24px}
  .addbar{display:flex;gap:10px;margin-bottom:10px}
  .search{flex:1;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:9px;padding:9px 12px;font-size:13px}
  .btn{background:var(--accent);color:#04223b;border:none;border-radius:9px;padding:0 18px;font-weight:500;cursor:pointer}.btn:disabled{opacity:.5}
  .recents{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px}
  .chip{background:var(--card);border:1px solid var(--border);color:var(--muted);border-radius:8px;padding:5px 11px;font-size:12px;cursor:pointer;font-family:var(--mono)}
  .err{font-size:12px;margin-bottom:10px}.pad{padding:30px 0}
  .kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:14px}
  .kc{background:var(--card2);border-radius:12px;padding:13px 15px}
  .kl{color:var(--muted);font-size:12px;margin-bottom:6px}.kv{font-size:20px}.kd{font-size:11px;margin-top:4px}
  .tw{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px}
  th{color:var(--dim);font-weight:400;text-align:left;padding:7px 10px;font-size:11px;white-space:nowrap}
  td{padding:9px 10px;border-top:1px solid var(--border);white-space:nowrap}
  .r{text-align:right}.sym{font-weight:500}
  @media(max-width:600px){.kpis{grid-template-columns:1fr}}
</style>
