<script>
  import { onMount } from 'svelte';
  import { loadHealth } from '$lib/data.js';
  import { NODES, nodeStatus } from '$lib/health-graph.js';
  import DependencyGraph from '$lib/components/DependencyGraph.svelte';

  // Health of the data pipeline: every collector as a node, colored by freshness,
  // wired by the dependencies that feed the AI Desk. Freshness is recomputed in the
  // browser against updated_at (like /brief), so it stays honest between snapshot runs.
  let st = $state('loading');
  let generated = $state('');
  let statusOf = $state({});
  let rows = $state([]);

  const LABEL = { ok: 'свежие', stale: 'устарело', missing: 'нет файла', error: 'ошибка', unknown: 'нет данных' };

  onMount(() => {
    (async () => {
      const h = await loadHealth();
      if (!h?.sources) { st = 'error'; return; }
      generated = h.generated_at || '';
      const now = Date.now();
      const so = {};
      for (const k of Object.keys(NODES)) {
        const src = h.sources[k];
        so[k] = { ...(src || {}), status: nodeStatus(src, now) };
      }
      statusOf = so;
      rows = Object.keys(NODES).map((k) => ({ key: k, label: NODES[k], ...so[k] }));
      st = 'ready';
    })();
  });

  const issues = $derived(rows.filter((r) => r.status !== 'ok'));
  const okCount = $derived(rows.length - issues.length);
  const fmtAge = (a) => (a == null ? '—' : a < 1 ? `${Math.round(a * 60)} мин` : `${a.toFixed(1)} ч`);
</script>

<svelte:head><title>Здоровье данных — TON Quant</title></svelte:head>

<header class="hd">
  <h1>Здоровье данных</h1>
  {#if generated}<span class="muted upd">снимок {generated}</span>{/if}
  <p class="muted lead">Каждый коллектор — узел, цвет = свежесть. Стрелки — зависимости: из чего считается каждый источник и что в итоге питает AI-деск. Свежесть пересчитывается в браузере, поэтому не «замерзает» между сборками.</p>
</header>

{#if st === 'loading'}
  <div class="muted pad">Загружаю health.json…</div>
{:else if st === 'error'}
  <div class="card bad">health.json недоступен — граф не построить.</div>
{:else}
  <section class="summary {issues.length ? 'warn' : 'ok'}">
    <i class="ti {issues.length ? 'ti-alert-triangle' : 'ti-circle-check'}"></i>
    {#if issues.length}
      <span>Требует внимания: {issues.map((r) => `${r.label} — ${LABEL[r.status] || r.status}`).join(' · ')}</span>
    {:else}
      <span>Все {okCount} источников свежие.</span>
    {/if}
  </section>

  <section class="card">
    <DependencyGraph {statusOf} />
    <div class="legend">
      <span><i class="dot ok"></i>свежие</span>
      <span><i class="dot stale"></i>устарело</span>
      <span><i class="dot bad"></i>ошибка / нет файла</span>
      <span><i class="dot unknown"></i>нет данных</span>
    </div>
  </section>

  <section class="card">
    <div class="sec-title">Источники <span class="muted">· {rows.length}</span></div>
    <table>
      <thead><tr><th>Источник</th><th>Статус</th><th class="num">Записей</th><th class="num">Возраст</th><th class="num">Лимит</th></tr></thead>
      <tbody>
        {#each rows as r}
          <tr>
            <td>{r.label} <span class="muted mono">{r.key}</span></td>
            <td><span class="st {r.status}">{LABEL[r.status] || r.status}</span></td>
            <td class="num mono">{r.count ?? '—'}</td>
            <td class="num mono">{fmtAge(r.age_h)}</td>
            <td class="num mono">{r.max_age_h ?? '—'} ч</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>
{/if}

<style>
  .summary { display: flex; align-items: center; gap: 9px; padding: 10px 13px; border-radius: 10px; margin: 12px 0; font-size: 14px; }
  .summary.ok { background: rgba(46, 190, 122, .10); color: var(--good); }
  .summary.warn { background: rgba(224, 168, 58, .12); color: var(--warn); }
  .legend { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 12px; color: var(--muted); font-size: 12px; }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .dot { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
  .dot.ok { background: var(--good); }
  .dot.stale { background: var(--warn); }
  .dot.bad { background: var(--bad); }
  .dot.unknown { background: var(--muted); }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--border); }
  th.num, td.num { text-align: right; }
  .mono { font-family: var(--mono); }
  .st.ok { color: var(--good); }
  .st.stale { color: var(--warn); }
  .st.error, .st.missing { color: var(--bad); }
  .st.unknown { color: var(--muted); }
</style>
