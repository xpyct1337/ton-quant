<script>
  import { onMount } from 'svelte';
  import { loadPaper, loadRegimeBench, liveRates } from '$lib/data.js';
  import { fmtUsd, fmtPct } from '$lib/format.js';
  import EquityChart from '$lib/components/EquityChart.svelte';

  const NAMES = { cons: 'Conservative', aggr: 'Aggressive', alt: 'Alt (CEX)' };
  const COLORS = { cons: '#22a7ff', aggr: '#f0997b', alt: '#b06bff' };
  const VERDICT = { edge: 'good', noise: 'bad', neutral: 'warn', collecting: 'muted' };

  let st = $state('loading');
  let bots = $state({});
  let scores = $state(null);
  let regime = $state(null);
  let bench = $state(null);
  let live = $state({});
  let showAll = $state(false);

  let series = $derived([
    ...Object.entries(bots).map(([n, b]) => ({ name: n, color: COLORS[n] || '#888', points: b.equity || [] })),
    ...(bench ? [{ name: 'bench', color: '#6b7280', dash: true, points: bench }] : [])
  ]);
  let trades = $derived(
    Object.entries(bots).flatMap(([n, b]) => (b.trades || []).map((t) => ({ ...t, bot: n })))
      .sort((a, b) => (a.closed < b.closed ? 1 : -1))
  );
  let positions = $derived(
    Object.entries(bots).flatMap(([n, b]) => (b.positions || []).map((p) => ({ ...p, bot: n })))
  );

  function kpi(b) {
    const eq = b.equity || [], cur = eq.length ? eq[eq.length - 1].v : 1000;
    const tr = b.trades || [];
    const wr = tr.length ? Math.round((tr.filter((t) => t.pnl > 0).length / tr.length) * 100) : null;
    return { cur, d: (cur / 1000 - 1) * 100, closed: tr.length, wr, open: (b.positions || []).length };
  }
  const sc = (s) => scores?.per_sig?.[s];
  const pnlOf = (p) => { const cur = live[p.addr]; return cur && p.entry_eff ? (cur / p.entry_eff - 1) * 100 : null; };

  onMount(async () => {
    try {
      const [p, rb] = await Promise.all([loadPaper(), loadRegimeBench()]);
      bots = p.bots; scores = p.scores; regime = rb.regime; bench = rb.bench;
      const addrs = positions.map((p) => p.addr);
      if (addrs.length) live = await liveRates([...new Set(addrs)]);
      st = Object.keys(bots).length ? 'ready' : 'empty';
    } catch (e) { st = 'error'; bots = { err: e.message }; }
  });
</script>

<header class="hd">
  <div class="hd-top"><h1>Paper bot</h1><span class="muted">виртуальные $1000 · сигналы · daily mark-to-market</span></div>
  <div class="legend">
    <span style="color:#22a7ff">■ Conservative</span><span style="color:#f0997b">■ Aggressive</span>
    <span style="color:#b06bff">■ Alt</span><span class="muted">┄ Buy&amp;Hold CORE</span>
  </div>
</header>

{#if st === 'loading'}<div class="muted pad">Загружаю состояние ботов…</div>
{:else if st === 'error'}<div class="card bad">Ошибка: {bots.err}</div>
{:else if st === 'empty'}<div class="muted pad">Данных пока нет — первый прогон в ожидании.</div>
{:else}
  <section class="kpis">
    {#each Object.entries(bots) as [n, b]}
      {@const k = kpi(b)}
      <div class="kc" style="border-top:3px solid {COLORS[n] || '#888'}">
        <div class="kl">{NAMES[n] || n}</div>
        <div class="kv mono" class:good={k.cur > 1000} class:bad={k.cur < 1000}>{fmtUsd(k.cur)}</div>
        <div class="kd muted">{fmtPct(k.d, 2)} · {k.closed} закрыто · WR {k.wr ?? '—'}{k.wr != null ? '%' : ''} · {k.open} откр.</div>
      </div>
    {/each}
    {#if bench}
      {@const bv = bench[bench.length - 1].v}
      <div class="kc" style="border-top:3px solid #6b7280">
        <div class="kl">Buy&amp;Hold (CORE)</div>
        <div class="kv mono" class:good={bv > 1000} class:bad={bv < 1000}>{fmtUsd(bv)}</div>
        <div class="kd muted">{fmtPct(bv / 1000 * 100 - 100, 2)} · equal-weight · пассив</div>
      </div>
    {/if}
    {#if regime}
      <div class="kc" style="border-top:3px solid {regime.regime === 'BULL' ? 'var(--good)' : regime.regime === 'BEAR' ? 'var(--bad)' : 'var(--warn)'}">
        <div class="kl">Market regime</div>
        <div class="kv" class:good={regime.regime === 'BULL'} class:bad={regime.regime === 'BEAR'} class:warn={regime.regime === 'NEUTRAL'}>{regime.regime}</div>
        <div class="kd muted">{regime.breadth}% CORE выше 7d avg · med 7d {regime.med7 != null ? fmtPct(regime.med7) : '—'}</div>
      </div>
    {/if}
  </section>

  <section class="card"><div class="sec-title">Equity curves</div><EquityChart {series} /></section>

  {#if positions.length}
    <section>
      <h2 class="sec-title">Открытые позиции · live PnL</h2>
      <div class="card"><table>
        <thead><tr><th>Bot</th><th>Jetton</th><th>Сигнал</th><th>Открыта</th><th class="r">Live Δ</th><th class="r">Unr. PnL</th></tr></thead>
        <tbody>
          {#each positions as p}
            {@const r = pnlOf(p)}
            <tr><td class="muted">{NAMES[p.bot] || p.bot}</td><td class="sym">{p.sym}</td>
              <td class="muted">{p.signal.replace(/_/g, ' ')}</td><td class="muted">{p.opened}</td>
              <td class="r mono" class:good={r > 0} class:bad={r < 0}>{r == null ? 'n/a' : fmtPct(r)}</td>
              <td class="r mono" class:good={r > 0} class:bad={r < 0}>{r == null ? 'n/a' : fmtUsd(p.size * r / 100)}</td></tr>
          {/each}
        </tbody>
      </table></div>
    </section>
  {/if}

  {#if scores?.per_sig}
    <section>
      <h2 class="sec-title">Signal scoreboard <span class="muted">· forward outcomes (no stops/costs); verdict при n≥5 на 3d</span></h2>
      <div class="card tw"><table>
        <thead><tr><th>Сигнал</th><th class="r">1d WR</th><th class="r">1d avg</th><th class="r">3d WR</th><th class="r">3d avg</th><th class="r">n</th><th>Verdict</th></tr></thead>
        <tbody>
          {#each Object.entries(scores.per_sig) as [name, s]}
            <tr><td class="sym">{name.replace(/_/g, ' ')}</td>
              <td class="r mono">{s.h1?.wr != null ? s.h1.wr + '%' : '—'}</td>
              <td class="r mono" class:good={s.h1?.avg > 0} class:bad={s.h1?.avg < 0}>{s.h1?.avg != null ? fmtPct(s.h1.avg) : '—'}</td>
              <td class="r mono">{s.h3?.wr != null ? s.h3.wr + '%' : '—'}</td>
              <td class="r mono" class:good={s.h3?.avg > 0} class:bad={s.h3?.avg < 0}>{s.h3?.avg != null ? fmtPct(s.h3.avg) : '—'}</td>
              <td class="r mono">{s.h3?.n ?? 0}</td>
              <td><span class="pill {VERDICT[s.verdict] || 'muted'}">{s.verdict}</span></td></tr>
          {/each}
        </tbody>
      </table></div>
    </section>
  {/if}

  {#if trades.length}
    <section>
      <h2 class="sec-title">Trade log</h2>
      <div class="card tw"><table>
        <thead><tr><th>Bot</th><th>Jetton</th><th>Сигнал</th><th>Закрыта</th><th class="r">Return</th><th class="r">PnL</th><th>Причина</th></tr></thead>
        <tbody>
          {#each (showAll ? trades : trades.slice(0, 10)) as t}
            <tr><td class="muted">{NAMES[t.bot] || t.bot}</td><td class="sym">{t.sym}</td>
              <td class="muted">{t.signal.replace(/_/g, ' ')}</td><td class="muted">{t.closed}</td>
              <td class="r mono" class:good={t.ret > 0} class:bad={t.ret < 0}>{fmtPct(t.ret)}</td>
              <td class="r mono" class:good={t.pnl > 0} class:bad={t.pnl < 0}>{fmtUsd(t.pnl)}</td>
              <td class="muted">{t.reason}</td></tr>
          {/each}
        </tbody>
      </table>
      {#if trades.length > 10}<button class="more" onclick={() => (showAll = !showAll)}>{showAll ? 'Свернуть' : `Показать все (${trades.length})`}</button>{/if}
      </div>
    </section>
  {/if}
{/if}

<style>
  .hd{margin-bottom:18px}.hd-top{display:flex;align-items:baseline;gap:12px}h1{font-size:24px}
  .legend{display:flex;gap:16px;margin-top:10px;font-size:12px;flex-wrap:wrap}
  .pad{padding:30px 0}section{margin-bottom:22px}
  .kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-bottom:6px}
  .kc{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 14px}
  .kl{color:var(--muted);font-size:12px;margin-bottom:6px}.kv{font-size:20px}.kd{font-size:11px;margin-top:5px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th{color:var(--dim);font-weight:400;text-align:left;padding:7px 9px;font-size:11px;white-space:nowrap}
  td{padding:8px 9px;border-top:1px solid var(--border);white-space:nowrap}
  .r{text-align:right}.sym{font-weight:500}.tw{overflow-x:auto}
  .pill{font-size:11px;padding:2px 9px;border-radius:6px;background:var(--card2)}
  .pill.good{color:var(--good)}.pill.bad{color:var(--bad)}.pill.warn{color:var(--warn)}.pill.muted{color:var(--muted)}
  .more{margin-top:10px;background:transparent;border:1px solid var(--border);color:var(--muted);border-radius:8px;padding:7px 14px;font-size:12px;cursor:pointer}
</style>
