<script>
  import { onMount } from 'svelte';
  import { loadXsForward } from '$lib/data.js';
  import EquityChart from '$lib/components/EquityChart.svelte';
  import StaleBanner from '$lib/components/StaleBanner.svelte';

  const HOLDS_PER_YEAR = 182.5; // 2-day hold (H=12 × 4H bars)
  let st = $state('loading');
  let data = $state(null);

  const sym = (n) => n.split('-')[0];
  const day = (ts) => new Date(ts).toISOString().slice(0, 10);
  const pct = (x) => (x > 0 ? '+' : '') + (x * 100).toFixed(2) + '%';
  const dur = (a, b) => Math.round((b - a) / 86400000) + 'd';

  let recs = $derived(data?.records || []);
  let nets = $derived(recs.map((r) => r.net));
  let cum = $derived(nets.reduce((a, x) => a * (1 + x), 1) - 1);
  let mean = $derived(nets.length ? nets.reduce((a, b) => a + b, 0) / nets.length : 0);
  let sd = $derived(
    nets.length > 1 ? Math.sqrt(nets.reduce((a, x) => a + (x - mean) ** 2, 0) / nets.length) : 0
  );
  let sharpe = $derived(sd > 0 ? (mean / sd) * Math.sqrt(HOLDS_PER_YEAR) : 0);
  let winRate = $derived(nets.length ? nets.filter((x) => x > 0).length / nets.length : 0);

  // Equity curve (base 1.0)
  let curve = $derived.by(() => {
    let e = 1, pts = [1];
    for (const x of nets) { e *= 1 + x; pts.push(e); }
    return pts;
  });

  // Max drawdown from equity curve
  let maxDd = $derived.by(() => {
    let peak = 1, dd = 0;
    for (const e of curve) { peak = Math.max(peak, e); dd = Math.min(dd, (e - peak) / peak); }
    return dd;
  });

  // Best / worst hold
  let bestRec = $derived(recs.length ? recs.reduce((a, b) => b.net > a.net ? b : a) : null);
  let worstRec = $derived(recs.length ? recs.reduce((a, b) => b.net < a.net ? b : a) : null);

  // EquityChart series: base-1000, one point per closed hold (at close_ts date)
  let eqSeries = $derived.by(() => {
    if (recs.length < 2) return [];
    let e = 1000;
    const pts = [{ d: day(recs[0].open_ts), v: 1000 }];
    for (const r of recs) { e *= 1 + r.net; pts.push({ d: day(r.close_ts), v: Math.round(e * 10) / 10 }); }
    return [{ name: 'XS-Mom', color: cum >= 0 ? '#41d68a' : '#ff6b6b', dash: false, points: pts }];
  });

  let state = $derived(data?.state || null);
  // Entry prices lookup: sym → price
  let entry = $derived(state?.entry || {});

  onMount(async () => {
    try {
      data = await loadXsForward();
      st = 'ready';
    } catch (e) {
      st = 'error';
    }
  });
</script>

<svelte:head><title>TON Quant — Momentum</title></svelte:head>

<header class="hd">
  <div class="hd-top">
    <h1>Cross-sectional momentum</h1>
    <span class="muted small">live paper forward-test — long топ-квинтиль / шорт нижний-квинтиль по 20-барному моментуму (4H), долларово-нейтрально, point-in-time топ-40 перпов по обороту, холд 2 дня, нетто комиссий</span>
  </div>
</header>

{#if st === 'loading'}<div class="muted pad">Загружаю трек-рекорд…</div>
{:else if st === 'error'}<div class="card bad">Не удалось загрузить forward-test.</div>
{:else}

  <StaleBanner when={state?.bar_ts ? state.bar_ts / 1000 : (recs.at(-1)?.close_ts ? recs.at(-1).close_ts / 1000 : null)} maxHours={54} what="прогон xs_forward" />

  {#if recs.length}
    <section class="kpis">
      <div class="kpi"><span class="kl">закрытых холдов</span><span class="kv">{recs.length}</span></div>
      <div class="kpi"><span class="kl">кумулятивно (нетто)</span><span class="kv" class:up={cum > 0} class:dn={cum < 0}>{pct(cum)}</span></div>
      <div class="kpi"><span class="kl">annualized Sharpe</span><span class="kv" class:up={sharpe > 0} class:dn={sharpe < 0}>{sharpe.toFixed(2)}</span></div>
      <div class="kpi"><span class="kl">hit-rate</span><span class="kv">{Math.round(winRate * 100)}%</span></div>
      <div class="kpi"><span class="kl">max drawdown</span><span class="kv" class:dn={maxDd < -0.001}>{maxDd < -0.001 ? pct(maxDd) : '—'}</span></div>
      <div class="kpi"><span class="kl">ср. холд</span><span class="kv" class:up={mean > 0} class:dn={mean < 0}>{pct(mean)}</span></div>
    </section>

    {#if eqSeries.length}
      <section class="card">
        <div class="ch-h muted small">эквити (нетто, база 1000 → {curve.at(-1).toFixed(3)})</div>
        <EquityChart series={eqSeries} />
      </section>
    {:else}
      <!-- single hold: just show a sparkline hint -->
      <section class="card">
        <div class="ch-h muted small">эквити появится после 2+ закрытых холдов</div>
      </section>
    {/if}
  {:else}
    <div class="card note">
      <b>Трек-рекорд пуст.</b> Forward-test запускается ежедневно через GitHub Actions; первая закрытая сделка появится после первого 2-дневного холда.
    </div>
  {/if}

  {#if state}
    <section class="card basket">
      <div class="bk-h"><i class="ti ti-target-arrow"></i> Текущая корзина <span class="muted small">сформирована {day(state.bar_ts)}</span></div>
      <div class="legs">
        <div class="leg">
          <div class="leg-h up">LONG · {state.long.length}</div>
          <div class="chips">
            {#each state.long as n}
              {@const s = sym(n)}
              <span class="chip long" title={entry[n] ? 'вход @ ' + entry[n] : ''}>
                {s}{#if entry[n]}<span class="ep">@ {entry[n] < 1 ? entry[n].toFixed(5) : entry[n].toFixed(4)}</span>{/if}
              </span>
            {/each}
          </div>
        </div>
        <div class="leg">
          <div class="leg-h dn">SHORT · {state.short.length}</div>
          <div class="chips">
            {#each state.short as n}
              {@const s = sym(n)}
              <span class="chip short" title={entry[n] ? 'вход @ ' + entry[n] : ''}>
                {s}{#if entry[n]}<span class="ep">@ {entry[n] < 1 ? entry[n].toFixed(5) : entry[n].toFixed(4)}</span>{/if}
              </span>
            {/each}
          </div>
        </div>
      </div>
    </section>
  {/if}

  {#if recs.length}
    <section class="card">
      <div class="bk-h"><i class="ti ti-history"></i> Закрытые холды</div>
      {#if bestRec && worstRec && recs.length > 1}
        <div class="bw muted small">Лучший: <span class="up">{pct(bestRec.net)}</span> · Худший: <span class="dn">{pct(worstRec.net)}</span></div>
      {/if}
      <div class="rows">
        {#each [...recs].reverse() as r}
          <div class="row">
            <span class="dt mono">{day(r.open_ts)} → {day(r.close_ts)}</span>
            <span class="dur muted mono">{dur(r.open_ts, r.close_ts)}</span>
            <span class="net mono" class:up={r.net > 0} class:dn={r.net < 0}>{pct(r.net)}</span>
            <span class="bk muted small">L: {r.long.map(sym).join(' ')} · S: {r.short.map(sym).join(' ')}</span>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  <p class="muted small foot">Стратегия — кросс-секционный моментум на перпах OKX (research: <span class="mono">scripts/xs_momentum.py</span>, бэктест Sharpe ~1.5, PBO 0.21 в −46% медвежьем режиме). Эта страница показывает <b>живой out-of-sample</b> forward-test (<span class="mono">scripts/xs_forward.py</span>) — единственное лекарство от оговорки «один медвежий режим в бэктесте»: каждый прогон закрывает корзину после 2-дневного холда и пишет реализованный нетто-спред в трек-рекорд. PAPER ONLY, без ордеров. Sharpe/кумулятив наполняются по календарному времени.</p>
{/if}

<style>
  .hd{margin-bottom:16px}
  .hd-top{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
  h1{font-family:var(--head);font-size:22px;margin:0}
  .small{font-size:12px}
  .pad{padding:20px 0}
  .card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 14px;margin-bottom:14px}
  .bad{color:#ff6b6b}
  .note{border-color:rgba(34,167,255,.35);background:rgba(34,167,255,.05)}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:14px}
  .kpi{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:11px 13px;display:flex;flex-direction:column;gap:3px}
  .kl{font-size:11px;color:var(--muted)}
  .kv{font-family:var(--head);font-size:20px;font-weight:600}
  .up{color:#41d68a}
  .dn{color:#ff6b6b}
  .kv.up{color:#41d68a}
  .kv.dn{color:#ff6b6b}
  .ch-h{margin-bottom:6px}
  .basket .bk-h{margin-bottom:10px}
  .bk-h{font-family:var(--head);font-size:14px;display:flex;align-items:center;gap:6px}
  .legs{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  @media(max-width:560px){.legs{grid-template-columns:1fr}}
  .leg-h{font-size:12px;font-weight:600;margin-bottom:6px}
  .leg-h.up{color:#41d68a}
  .leg-h.dn{color:#ff6b6b}
  .chips{display:flex;flex-wrap:wrap;gap:6px}
  .chip{font-size:11px;padding:3px 8px;border-radius:6px;background:rgba(255,255,255,.05);color:var(--muted);display:flex;flex-direction:column;align-items:center;gap:1px}
  .chip.long{background:rgba(65,214,138,.13);color:#41d68a}
  .chip.short{background:rgba(255,107,107,.12);color:#ff6b6b}
  .ep{font-size:9px;opacity:.7;font-family:ui-monospace,Menlo,Consolas,monospace}
  .bw{margin-bottom:8px}
  .rows{display:flex;flex-direction:column;gap:6px}
  .row{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;padding:5px 0;border-bottom:1px solid var(--border)}
  .row:last-child{border-bottom:none}
  .dt{font-size:12px;color:var(--text);min-width:160px}
  .dur{font-size:11px;min-width:22px}
  .net{font-size:13px;font-weight:600;min-width:64px}
  .net.up{color:#41d68a}
  .net.dn{color:#ff6b6b}
  .bk{flex:1;min-width:0}
  .mono{font-family:ui-monospace,Menlo,Consolas,monospace}
  .foot{margin-top:16px;max-width:720px;line-height:1.5}
</style>
