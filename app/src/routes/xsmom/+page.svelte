<script>
  import { onMount } from 'svelte';
  import { loadXsForward } from '$lib/data.js';

  const HOLDS_PER_YEAR = 182.5; // 2-day hold (H=12 × 4H bars)
  let st = $state('loading');
  let data = $state(null);

  const sym = (n) => n.split('-')[0];
  const day = (ts) => new Date(ts).toISOString().slice(0, 10);
  const pct = (x) => (x > 0 ? '+' : '') + (x * 100).toFixed(2) + '%';

  let recs = $derived(data?.records || []);
  let nets = $derived(recs.map((r) => r.net));
  let cum = $derived(nets.reduce((a, x) => a * (1 + x), 1) - 1);
  let mean = $derived(nets.length ? nets.reduce((a, b) => a + b, 0) / nets.length : 0);
  // population std (ddof=0) to match xs_forward.py's np.std Sharpe in the run logs
  let sd = $derived(
    nets.length > 1 ? Math.sqrt(nets.reduce((a, x) => a + (x - mean) ** 2, 0) / nets.length) : 0
  );
  let sharpe = $derived(sd > 0 ? (mean / sd) * Math.sqrt(HOLDS_PER_YEAR) : 0);
  let winRate = $derived(nets.length ? nets.filter((x) => x > 0).length / nets.length : 0);

  // equity curve points (base 1.0) -> SVG polyline
  let curve = $derived.by(() => {
    let e = 1, pts = [1];
    for (const x of nets) { e *= 1 + x; pts.push(e); }
    return pts;
  });
  let spark = $derived.by(() => {
    if (curve.length < 2) return '';
    const W = 560, H = 90, lo = Math.min(...curve), hi = Math.max(...curve), rng = hi - lo || 1;
    return curve.map((v, i) =>
      `${(i / (curve.length - 1)) * W},${H - ((v - lo) / rng) * H}`).join(' ');
  });

  let state = $derived(data?.state || null);

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
  <div class="hd-top"><h1>Cross-sectional momentum</h1>
    <span class="muted">live paper forward-test — long топ-квинтиль / шорт нижний-квинтиль по 20-барному моментуму (4H), долларово-нейтрально, point-in-time топ-40 перпов по обороту, холд 2 дня, нетто комиссий</span>
  </div>
</header>

{#if st === 'loading'}<div class="muted pad">Загружаю трек-рекорд…</div>
{:else if st === 'error'}<div class="card bad">Не удалось загрузить forward-test.</div>
{:else}
  {#if recs.length}
    <section class="kpis">
      <div class="kpi"><span class="kl">закрытых холдов</span><span class="kv">{recs.length}</span></div>
      <div class="kpi"><span class="kl">кумулятивно (нетто)</span><span class="kv" class:up={cum > 0} class:down={cum < 0}>{pct(cum)}</span></div>
      <div class="kpi"><span class="kl">annualized Sharpe</span><span class="kv" class:up={sharpe > 0} class:down={sharpe < 0}>{sharpe.toFixed(2)}</span></div>
      <div class="kpi"><span class="kl">hit-rate</span><span class="kv">{Math.round(winRate * 100)}%</span></div>
      <div class="kpi"><span class="kl">последний холд</span><span class="kv" class:up={nets.at(-1) > 0} class:down={nets.at(-1) < 0}>{pct(nets.at(-1))}</span></div>
    </section>

    {#if spark}
      <section class="card">
        <div class="ch-h muted small">эквити (нетто, база 1.00 → {curve.at(-1).toFixed(3)})</div>
        <svg class="spark" viewBox="0 0 560 90" preserveAspectRatio="none">
          <polyline points={spark} fill="none" stroke={cum >= 0 ? '#41d68a' : '#ff6b6b'} stroke-width="1.5" vector-effect="non-scaling-stroke" />
        </svg>
      </section>
    {/if}
  {:else}
    <div class="card note">
      <b>Трек-рекорд пуст.</b> Forward-test запускается ежедневно через GitHub Actions; первая закрытая сделка появится после первого 2-дневного холда. Ниже — текущая корзина, как только скрипт впервые отработает.
    </div>
  {/if}

  {#if state}
    <section class="card basket">
      <div class="bk-h"><i class="ti ti-target-arrow"></i> Текущая корзина <span class="muted small">сформирована {day(state.bar_ts)}</span></div>
      <div class="legs">
        <div class="leg">
          <div class="leg-h up">LONG · {state.long.length}</div>
          <div class="chips">{#each state.long as n}<span class="chip long">{sym(n)}</span>{/each}</div>
        </div>
        <div class="leg">
          <div class="leg-h down">SHORT · {state.short.length}</div>
          <div class="chips">{#each state.short as n}<span class="chip short">{sym(n)}</span>{/each}</div>
        </div>
      </div>
    </section>
  {/if}

  {#if recs.length}
    <section class="card">
      <div class="bk-h"><i class="ti ti-history"></i> Закрытые холды</div>
      <div class="rows">
        {#each [...recs].reverse() as r}
          <div class="row">
            <span class="dt mono">{day(r.open_ts)} → {day(r.close_ts)}</span>
            <span class="net mono" class:up={r.net > 0} class:down={r.net < 0}>{pct(r.net)}</span>
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
  .kv.up,.net.up,.leg-h.up{color:#41d68a}
  .kv.down,.net.down,.leg-h.down{color:#ff6b6b}
  .ch-h{margin-bottom:6px}
  .spark{width:100%;height:90px;display:block}
  .basket .bk-h{margin-bottom:10px}
  .bk-h{font-family:var(--head);font-size:14px;display:flex;align-items:center;gap:6px}
  .legs{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  @media(max-width:560px){.legs{grid-template-columns:1fr}}
  .leg-h{font-size:12px;font-weight:600;margin-bottom:6px}
  .chips{display:flex;flex-wrap:wrap;gap:4px}
  .chip{font-size:11px;padding:2px 7px;border-radius:6px;background:rgba(255,255,255,.05);color:var(--muted)}
  .chip.long{background:rgba(65,214,138,.13);color:#41d68a}
  .chip.short{background:rgba(255,107,107,.12);color:#ff6b6b}
  .rows{display:flex;flex-direction:column;gap:6px}
  .row{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;padding:5px 0;border-bottom:1px solid var(--border)}
  .row:last-child{border-bottom:none}
  .dt{font-size:12px;color:var(--text);min-width:160px}
  .net{font-size:13px;font-weight:600;min-width:64px}
  .bk{flex:1;min-width:0}
  .mono{font-family:ui-monospace,Menlo,Consolas,monospace}
  .foot{margin-top:16px;max-width:720px;line-height:1.5}
</style>
