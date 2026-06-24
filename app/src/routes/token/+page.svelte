<script>
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { base } from '$app/paths';
  import { loadToken, loadTrades } from '$lib/data.js';
  import { fmtUsd, fmtPct, fmtNum, shortAddr } from '$lib/format.js';
  import { human } from '$lib/token.js';
  import PriceChart from '$lib/components/PriceChart.svelte';
  import StackedBar from '$lib/components/StackedBar.svelte';

  let st = $state('loading');
  let d = $state(null);
  let err = $state('');
  let showAll = $state(false);
  let unitTon = $state(false);
  let trades = $state([]);

  let d24 = $derived.by(() => {
    const c = d?.chart || []; if (c.length < 2) return null;
    const cur = c[c.length - 1].v, prev = c[Math.max(0, c.length - 2)].v;
    return prev > 0 ? (cur / prev - 1) * 100 : null;
  });

  let thesis = $derived.by(() => {
    if (!d) return '';
    const parts = [];
    parts.push(d.score.score >= 70 ? 'Сильные фундаменталы' : d.score.score >= 45 ? 'Смешанные фундаменталы' : 'Слабые фундаменталы');
    if (d.mvrv != null) parts.push(d.mvrv > 1.2 ? 'цена заметно выше средней себестоимости (зона прибыли/перегрева)' : d.mvrv < 0.9 ? 'цена ниже себестоимости (капитуляция/недооценка)' : 'цена у средней себестоимости');
    parts.push(d.tiers.verdict === 'Whale-dominated' ? 'держатели сконцентрированы у китов' : d.tiers.verdict === 'Distributed' ? 'держатели распределены' : 'смешанная концентрация');
    const edgeHit = d.edge.find((e) => e.verdict === 'edge');
    if (edgeHit) parts.push(`наш сигнал «${edgeHit.sig}» исторически с edge`);
    return parts.join(' · ') + '.';
  });

  const ago = (ts) => { const s = (Date.now() - new Date(ts).getTime()) / 1000; return s < 60 ? Math.round(s) + 's' : s < 3600 ? Math.round(s / 60) + 'm' : s < 86400 ? Math.round(s / 3600) + 'h' : Math.round(s / 86400) + 'd'; };

  onMount(async () => {
    const a = $page.url.searchParams.get('a');
    if (!a) { st = 'noaddr'; return; }
    try { d = await loadToken(a); st = 'ready'; loadTrades(a).then((t) => (trades = t)).catch(() => {}); } catch (e) { err = e.message; st = 'error'; }
  });
</script>

<svelte:head><title>{d ? d.name + ' — TON Quant' : 'Token — TON Quant'}</title></svelte:head>

{#if st === 'loading'}<div class="muted pad">Загружаю onchain-данные жетона…</div>
{:else if st === 'noaddr'}
  <div class="card"><h2 class="sec-title">Адрес жетона не указан</h2><p class="muted">Открой страницу как <code>/token?a=ADDRESS</code> — или выбери жетон на <a href="{base}/">Markets</a>.</p></div>
{:else if st === 'error'}<div class="card bad">Ошибка: {err}</div>
{:else}
  <header class="hero">
    <div class="hl">
      {#if d.image}<img class="ava" src={d.image} alt="" />{/if}
      <div>
        <div class="nm"><h1>{d.name}</h1><span class="sym muted">{d.symbol}</span></div>
        <div class="tags">
          {#if d.verification === 'whitelist'}<span class="pill good">verified</span>{/if}
          {#if d.verification === 'blacklist'}<span class="pill bad">blacklisted</span>{/if}
          {#if d.adminZero}<span class="pill good">mint renounced</span>{:else}<span class="pill warn">mint active</span>{/if}
          {#if d.taxable}<span class="pill warn">taxable</span>{/if}
          {#if d.lowLiq}<span class="pill warn">low liquidity</span>{/if}
          <span class="addr muted mono">{shortAddr(d.addr)}</span>
        </div>
      </div>
    </div>
    <div class="hr">
      <div class="score" class:good={d.score.score >= 70} class:warn={d.score.score >= 45 && d.score.score < 70} class:bad={d.score.score < 45}>
        <div class="snum mono">{d.score.score}</div><div class="slbl muted">TON Quant Score</div>
      </div>
      <div class="price">
        <button class="unit" onclick={() => (unitTon = !unitTon)}>{unitTon ? 'TON' : 'USD'}</button>
        <div class="pv mono">{unitTon ? (d.priceTon != null ? d.priceTon.toPrecision(4) + ' TON' : '—') : fmtUsd(d.price)}</div>
        {#if d24 != null}<div class="pd mono" class:good={d24 > 0} class:bad={d24 < 0}>{fmtPct(d24)}</div>{/if}
      </div>
    </div>
  </header>

  <div class="thesis"><i class="ti ti-bulb"></i><span>{thesis}</span></div>

  <section class="kpis">
    <div class="kc"><div class="kl">Market cap</div><div class="kv mono">{fmtUsd(d.mcap)}</div></div>
    <div class="kc"><div class="kl">Holders</div><div class="kv mono">{fmtNum(d.holders)}</div>{#if d.growth}<div class="kd mono" class:good={d.growth.pct > 0} class:bad={d.growth.pct < 0}>{d.growth.pct >= 0 ? '▲' : '▼'}{Math.abs(d.growth.pct).toFixed(1)}% {d.growth.days}d</div>{/if}</div>
    <div class="kc"><div class="kl">DEX liquidity</div><div class="kv mono">{fmtUsd(d.liq)}</div></div>
    <div class="kc"><div class="kl">Volume 24h</div><div class="kv mono">{fmtUsd(d.vol)}</div></div>
    <div class="kc"><div class="kl">Top-10 hold</div><div class="kv mono">{d.top10 != null ? d.top10.toFixed(1) + '%' : '—'}</div></div>
    <div class="kc"><div class="kl">MVRV-lite</div><div class="kv mono" class:good={d.mvrv > 1} class:bad={d.mvrv < 1}>{d.mvrv != null ? d.mvrv.toFixed(2) : '—'}</div></div>
  </section>

  <!-- THE leap: quant synthesis -->
  <section class="grid2">
    <div class="card">
      <div class="sec-title">Cost-basis · MVRV-lite</div>
      <div class="big mono" class:good={d.mvrv > 1} class:bad={d.mvrv < 1}>{d.mvrv != null ? d.mvrv.toFixed(2) + '×' : '—'}</div>
      <p class="muted sm">{d.mvrv == null ? 'мало истории цены' : d.mvrv > 1.2 ? 'Рынок торгуется выше средней себестоимости держателей — массовая нереализованная прибыль (риск фиксации).' : d.mvrv < 0.9 ? 'Рынок ниже средней себестоимости — держатели в среднем в минусе (зона капитуляции).' : 'Рынок у средней себестоимости — равновесие.'}</p>
      {#if d.inProfit != null}<div class="profitbar"><div class="pf" style="width:{d.inProfit}%"></div></div><div class="muted sm">≈{d.inProfit.toFixed(0)}% окна истории ниже текущей цены (proxy «в прибыли»)</div>{/if}
    </div>
    <div class="card">
      <div class="sec-title">Наш сигнал-трек на этом жетоне</div>
      {#if !d.curated}
        <p class="muted sm">Жетон не входит в отслеживаемые 24 — журнал сигналов/боты по нему не ведутся.</p>
      {:else if d.edge.length}
        {#each d.edge as e}
          <div class="edge"><span class="sym">{e.sig.replace(/_/g, ' ')}</span> <span class="pill {e.verdict === 'edge' ? 'good' : e.verdict === 'noise' ? 'bad' : 'muted'}">{e.verdict}</span>{#if e.d1 != null}<span class="muted mono">{fmtPct(e.d1)}</span>{/if}</div>
        {/each}
      {:else}<p class="muted sm">Сегодня сигналов нет. Жетон отслеживается — журнал копится.</p>{/if}
      <div class="sec-title" style="margin-top:14px">Paper-бот на этом жетоне</div>
      {#if d.track.n || d.track.positions.length}
        <div class="sm">Сделок: <b>{d.track.n}</b> · {d.track.wins}W/{d.track.losses}L · реализовано <span class="mono" class:good={d.track.realized > 0} class:bad={d.track.realized < 0}>{fmtUsd(d.track.realized)}</span>{#if d.track.positions.length} · открыто {d.track.positions.length}{/if}</div>
      {:else}<p class="muted sm">Боты пока не торговали этот жетон.</p>{/if}
    </div>
  </section>

  <section class="card"><div class="sec-title">Цена · {d.chart.length} точек</div>{#if d.chart.length > 2}<PriceChart points={d.chart} />{:else}<p class="muted sm">Недостаточно истории цены.</p>{/if}</section>

  <section class="card">
    <div class="sec-title">Структура держателей <span class="muted">· {d.tiers.verdict} ({d.tiers.whalePct.toFixed(0)}%)</span>{#if d.hhi}<span class="pill {d.hhi.cls}" style="margin-left:8px">HHI {d.hhi.label}</span>{/if}</div>
    <StackedBar buckets={d.tiers.buckets} />
  </section>

  <section class="card tw">
    <div class="sec-title">Топ держателей <span class="muted">· из топ-100 сэмпла</span></div>
    <table>
      <thead><tr><th>#</th><th>Адрес</th><th class="r">Баланс</th><th class="r">Доля</th></tr></thead>
      <tbody>
        {#each (showAll ? d.holdersList : d.holdersList.slice(0, 10)) as h, i}
          <tr><td class="muted">{i + 1}</td><td class="mono">{shortAddr(h.owner?.address || h.address)}</td>
            <td class="r mono">{fmtNum(human(h.balance, d.decimals))}</td>
            <td class="r mono">{(Number(h.balance) / (d.supply * Math.pow(10, d.decimals)) * 100).toFixed(2)}%</td></tr>
        {/each}
      </tbody>
    </table>
    {#if d.holdersList.length > 10}<button class="more" onclick={() => (showAll = !showAll)}>{showAll ? 'Свернуть' : `Показать все (${d.holdersList.length})`}</button>{/if}
  </section>

  {#if d.pairs.length}
    <section class="card tw">
      <div class="sec-title">DEX-ликвидность и слиппедж</div>
      <table>
        <thead><tr><th>Пул</th><th class="r">Liquidity</th><th class="r">Vol 24h</th><th class="r">$1K</th><th class="r">$10K</th><th class="r">Max &lt;1%</th></tr></thead>
        <tbody>
          {#each d.pairs.slice(0, 6) as p}
            {@const q = (p.liquidity?.usd || 0) / 2}
            <tr><td>{p.dexId || 'dex'} <span class="muted">{p.baseToken?.symbol}/{p.quoteToken?.symbol}</span></td>
              <td class="r mono">{fmtUsd(p.liquidity?.usd)}</td><td class="r mono">{fmtUsd(p.volume?.h24)}</td>
              <td class="r mono">{q > 0 ? ((Math.pow((q + 1000) / q, 2) - 1) * 100).toFixed(2) + '%' : '—'}</td>
              <td class="r mono">{q > 0 ? ((Math.pow((q + 10000) / q, 2) - 1) * 100).toFixed(2) + '%' : '—'}</td>
              <td class="r mono">{q > 0 ? fmtUsd(q * (Math.sqrt(1.01) - 1)) : '—'}</td></tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}

  {#if trades.length}
    <section class="card tw">
      <div class="sec-title">Свежие сделки на DEX <span class="muted">· реальные свопы (GeckoTerminal)</span></div>
      <table>
        <thead><tr><th>Время</th><th>Сторона</th><th class="r">Объём</th><th>Кошелёк</th></tr></thead>
        <tbody>
          {#each trades as t}
            <tr><td class="muted">{ago(t.ts)} назад</td>
              <td class="sym" class:good={t.kind === 'buy'} class:bad={t.kind === 'sell'}>{t.kind === 'buy' ? 'buy' : 'sell'}</td>
              <td class="r mono" class:good={t.kind === 'buy'} class:bad={t.kind === 'sell'}>{fmtUsd(t.usd)}</td>
              <td class="mono muted">{shortAddr(t.from)}</td></tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}
  <div class="foot muted">Данные: tonapi.io + DexScreener + STON.fi. Не финансовый совет.</div>
{/if}

<style>
  .pad{padding:30px 0}section{margin-bottom:16px}
  .hero{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;align-items:flex-start;margin-bottom:14px}
  .hl{display:flex;gap:14px;align-items:flex-start}
  .ava{width:52px;height:52px;border-radius:50%;background:var(--card2)}
  .nm{display:flex;align-items:baseline;gap:9px}h1{font-size:23px}.sym{font-size:14px}
  .tags{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px;align-items:center}
  .addr{font-size:12px}
  .hr{display:flex;gap:18px;align-items:center}
  .score{text-align:center}.snum{font-size:30px;font-weight:600}.slbl{font-size:10px}
  .score.good .snum{color:var(--good)}.score.warn .snum{color:var(--warn)}.score.bad .snum{color:var(--bad)}
  .price{text-align:right}.unit{background:var(--card2);border:none;color:var(--muted);font-size:11px;padding:2px 8px;border-radius:6px;cursor:pointer}
  .pv{font-size:24px;margin-top:3px}.pd{font-size:13px}
  .thesis{display:flex;gap:9px;align-items:flex-start;background:rgba(34,167,255,.08);border:1px solid rgba(34,167,255,.2);border-radius:11px;padding:11px 14px;margin-bottom:18px;font-size:13px;line-height:1.5}
  .thesis i{color:var(--accent);font-size:17px;flex:none;margin-top:1px}
  .kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:16px}
  .kc{background:var(--card2);border-radius:11px;padding:11px 13px}
  .kl{color:var(--muted);font-size:11px;margin-bottom:5px}.kv{font-size:17px}.kd{font-size:11px;margin-top:4px}
  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
  .big{font-size:34px;margin:4px 0 6px}.sm{font-size:13px;line-height:1.5}
  .profitbar{height:8px;border-radius:5px;background:rgba(255,255,255,.08);overflow:hidden;margin:8px 0 5px}.pf{height:100%;background:var(--good)}
  .edge{display:flex;align-items:center;gap:8px;padding:5px 0;font-size:13px}
  .pill{font-size:11px;padding:2px 9px;border-radius:6px;background:var(--card2)}
  .pill.good{color:var(--good)}.pill.bad{color:var(--bad)}.pill.warn{color:var(--warn)}.pill.muted{color:var(--muted)}
  table{width:100%;border-collapse:collapse;font-size:13px}.tw{overflow-x:auto}
  th{color:var(--dim);font-weight:400;text-align:left;padding:6px 9px;font-size:11px;white-space:nowrap}
  td{padding:8px 9px;border-top:1px solid var(--border);white-space:nowrap}
  .r{text-align:right}.sym{font-weight:500}
  .more{margin-top:10px;background:transparent;border:1px solid var(--border);color:var(--muted);border-radius:8px;padding:7px 14px;font-size:12px;cursor:pointer}
  .foot{font-size:11px;margin-top:18px}
  code{background:var(--card2);padding:1px 6px;border-radius:5px;font-family:var(--mono)}
  @media(max-width:720px){.kpis{grid-template-columns:repeat(3,1fr)}.grid2{grid-template-columns:1fr}}
</style>
