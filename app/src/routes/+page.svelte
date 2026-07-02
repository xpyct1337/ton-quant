<script>
  import { onMount } from 'svelte';
  import { loadAll, loadSignals, liveRates } from '$lib/data.js';
  import { coreIndex, breadth, overlayPrices } from '$lib/metrics.js';
  import { buildAgents } from '$lib/agents.js';
  import { buildUnlocks } from '$lib/unlocks.js';
  import { fmtUsd, fmtPct } from '$lib/format.js';
  import Treemap from '$lib/components/Treemap.svelte';
  import AgentCard from '$lib/components/AgentCard.svelte';
  import JettonTable from '$lib/components/JettonTable.svelte';
  import StaleBanner from '$lib/components/StaleBanner.svelte';

  let state = $state('loading');
  let rows = $state([]);
  let meta = $state({});
  let agents = $state([]);
  let unlocks = $state([]);
  let cat = $state('all');
  let snaps = [];

  const cats = [
    { id: 'all', label: 'Все' }, { id: 'meme', label: 'Memes' }, { id: 'defi', label: 'DeFi' },
    { id: 'stable', label: 'Stables' }, { id: 'staking', label: 'Staking' }
  ];

  let kpi = $derived.by(() => {
    if (!rows.length) return {};
    const tvl = rows.reduce((s, r) => s + (r.tvl || 0), 0);
    const vol = rows.reduce((s, r) => s + (r.vol24 || 0), 0);
    return { tvl, vol, index: coreIndex(rows), breadth: breadth(rows) };
  });
  let movers = $derived(
    [...rows].filter((r) => r.core && r.d7 != null).sort((a, b) => b.d7 - a.d7)
  );
  let tableRows = $derived(cat === 'all' ? rows : rows.filter((r) => r.cat === cat));

  // live price overlay — d1/d7 re-based to the snapshots nearest 24h/7d back,
  // so the shown price and the shown change always agree. Degrades silently.
  async function refreshLive() {
    if (!rows.length) return;
    const live = await liveRates(rows.map((r) => r.addr));
    const n = overlayPrices(rows, (a) => live[a], snaps, Date.now() / 1000);
    meta.live = n;
    meta.liveAt = n ? Date.now() : meta.liveAt;
  }

  onMount(() => {
    (async () => {
      try {
        const [d, sig] = await Promise.all([loadAll(), loadSignals()]);
        rows = d.rows;
        snaps = d.snaps;
        meta = { updated: d.updated, snaps: d.snapCount, intraday: d.intraday, curTs: d.curTs, live: 0 };
        agents = buildAgents({ rows: d.rows, signals: sig });
        unlocks = buildUnlocks(d.rows);
        state = 'ready';
        await refreshLive();
      } catch (e) {
        state = 'error';
        meta = { err: String(e.message || e) };
      }
    })();
    const iv = setInterval(() => { if (!document.hidden) refreshLive(); }, 60000);
    const onVis = () => { if (!document.hidden) refreshLive(); };
    document.addEventListener('visibilitychange', onVis);
    return () => { clearInterval(iv); document.removeEventListener('visibilitychange', onVis); };
  });
</script>

<header class="hd">
  <div class="hd-top">
    <h1>Markets</h1>
    {#if meta.live}<span class="live"><span class="dot"></span>live · 60s</span>
    {:else}<span class="live off">daily</span>{/if}
    {#if meta.updated}<span class="muted upd">snapshot {meta.updated}{meta.intraday ? ' +intraday' : ''} · {meta.snaps} дней{meta.live ? ' · live цены' : ''}</span>{/if}
  </div>
  <div class="tabs">
    {#each cats as c}
      <button class="tab" class:on={cat === c.id} onclick={() => (cat = c.id)}>{c.label}</button>
    {/each}
  </div>
</header>

{#if state === 'loading'}
  <div class="muted pad">Загружаю onchain-данные…</div>
{:else if state === 'error'}
  <div class="card bad">Не удалось загрузить данные: {meta.err}</div>
{:else}
  <StaleBanner when={meta.curTs} />
  <!-- Zone 1: bento overview -->
  <section class="bento">
    <div class="kpis">
      <div class="kpi"><div class="kl">DEX TVL</div><div class="kv mono">{fmtUsd(kpi.tvl)}</div></div>
      <div class="kpi"><div class="kl">Volume 24h</div><div class="kv mono">{fmtUsd(kpi.vol)}</div></div>
      <div class="kpi"><div class="kl">TON Core Index 7d</div><div class="kv mono" class:good={kpi.index > 0} class:bad={kpi.index < 0}>{fmtPct(kpi.index)}</div></div>
      <div class="kpi"><div class="kl">Breadth</div><div class="kv mono">{kpi.breadth ? `${kpi.breadth.above}/${kpi.breadth.total}` : '—'}</div></div>
    </div>
    <div class="card map">
      <div class="sec-title">Market map · CORE, площадь ≈ √mcap, цвет = 7d</div>
      <Treemap {rows} />
      <div class="movers">
        {#each [...movers.slice(0, 3), ...movers.slice(-3).reverse()] as m}
          <span class="mv" class:good={m.d7 > 0} class:bad={m.d7 < 0}>{m.sym} {fmtPct(m.d7)}</span>
        {/each}
      </div>
    </div>
  </section>

  <!-- Zone 2: agent feed -->
  <section>
    <h2 class="sec-title">Agent feed <span class="muted">· авто из сигналов, 3×/день</span></h2>
    {#if agents.length}
      <div class="agrid">{#each agents as c}<AgentCard card={c} />{/each}</div>
    {:else}<div class="muted pad">Сигналов нет — рынок спокоен.</div>{/if}
  </section>

  <!-- Zone 3: supply pressure -->
  <section>
    <h2 class="sec-title">Supply pressure <span class="muted">· эмиссия / стейкинг / приток</span></h2>
    {#if unlocks.length}
      <div class="card">
        <table class="ut">
          <thead><tr><th>Jetton</th><th>Событие</th><th class="r">Давление</th><th class="r">$ влияние</th></tr></thead>
          <tbody>
            {#each unlocks as u}
              <tr><td class="sym">{u.sym}</td><td class="muted">{u.event}</td>
                <td class="r"><div class="bar"><div class="fill" class:hi={u.pct > 40} style="width:{u.pct}%"></div></div><span class="mono pctn">{u.pct}%</span></td>
                <td class="r mono">{fmtUsd(u.usd)}</td></tr>
            {/each}
          </tbody>
        </table>
        <div class="note muted">ponytail: выводим только то, что считается client-side (unstake-окна, эмиссия). Точные team-cliff даты — n/a без внешнего расписания.</div>
      </div>
    {:else}<div class="muted pad">Нет заметного давления предложения.</div>{/if}
  </section>

  <!-- Zone 4: market internals -->
  <section>
    <h2 class="sec-title">Все jettons {cat !== 'all' ? '· ' + cats.find((c) => c.id === cat).label : ''}</h2>
    <JettonTable rows={tableRows} />
  </section>
{/if}

<style>
  .hd{margin-bottom:18px}
  .hd-top{display:flex;align-items:center;gap:12px}
  h1{font-size:24px}
  .live{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--accent);background:rgba(34,167,255,.12);padding:3px 9px;border-radius:6px}
  .live.off{color:var(--muted);background:rgba(255,255,255,.06)}
  .dot{width:6px;height:6px;border-radius:50%;background:var(--accent)}
  .upd{font-size:12px;margin-left:2px}
  .tabs{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
  .tab{background:transparent;border:none;color:var(--muted);padding:6px 2px;font-size:13px;cursor:pointer;border-bottom:2px solid transparent}
  .tab.on{color:var(--accent);border-bottom-color:var(--accent)}
  .pad{padding:30px 0}
  section{margin-bottom:26px}
  .bento{display:grid;grid-template-columns:1fr;gap:14px}
  .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
  .kpi{background:var(--card2);border-radius:12px;padding:13px 15px}
  .kl{color:var(--muted);font-size:12px;margin-bottom:6px}
  .kv{font-size:21px}
  .map{padding-bottom:12px}
  .movers{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
  .mv{font-family:var(--mono);font-size:12px;padding:3px 9px;border-radius:6px;background:var(--card2)}
  .agrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
  .ut{width:100%;border-collapse:collapse;font-size:13px}
  .ut th{color:var(--dim);font-weight:400;text-align:left;padding:6px 8px;font-size:11px}
  .ut td{padding:9px 8px;border-top:1px solid var(--border)}
  .ut .r{text-align:right}
  .sym{font-weight:500}
  .bar{display:inline-block;width:90px;height:6px;border-radius:4px;background:rgba(255,255,255,.08);overflow:hidden;vertical-align:middle;margin-right:8px}
  .fill{height:100%;background:var(--accent)}.fill.hi{background:var(--bad)}
  .pctn{font-size:12px;color:var(--muted)}
  .note{font-size:11px;margin-top:10px}
  @media(max-width:720px){.kpis{grid-template-columns:repeat(2,1fr)}}
</style>
