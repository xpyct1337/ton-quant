<script>
  import { onMount } from 'svelte';
  import { fmtUsd, fmtPct } from '$lib/format.js';
  import { perpRows, rankSignals, signalLabel, sparkPoints } from '$lib/perps.js';

  // Hyperliquid public info API: без ключа, CORS открыт, POST-запросы.
  // 2 запроса на обновление: метаданные+контексты всех перпов одним вызовом,
  // свечи только для фокусной монеты. Сигналы TG-каналов живут на /tgsig.
  const HL = 'https://api.hyperliquid.xyz/info';
  // Toncoin на Hyperliquid: тикер TON делистнут 21.06.2026, торгуется как GRAM.
  const FOCUS = 'GRAM';
  // api.hyperliquid.xyz гео-блокируется CloudFront'ом в ряде регионов — тогда
  // берём часовой снапшот воркера (scripts/perp_markets.py, perp-markets.yml).
  const MARKETS_URL = 'https://raw.githubusercontent.com/xpyct1337/ton-quant/main/data/perp_markets.json';

  let st = $state('loading');
  let err = $state('');
  let live = $state(true);   // false → рисуем из снапшота воркера
  let snap = null;           // кэш perp_markets.json на сессию
  let rows = $state([]);
  let longs = $state([]);
  let shorts = $state([]);
  let ton = $state(null);
  let spark = $state('');
  let updatedAt = $state(null);
  let busy = false;

  // 8s таймаут: DPI-блокировки часто не рвут соединение, а молча дропают
  // пакеты — без таймаута fetch висит минутами и фолбэк не наступает.
  const info = (body) =>
    fetch(HL, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body), signal: AbortSignal.timeout(8000) })
      .then((r) => { if (!r.ok) throw new Error('Hyperliquid HTTP ' + r.status); return r.json(); });

  function apply(meta, ctxs, ts) {
    const ranked = rankSignals(perpRows(meta, ctxs), 5);
    rows = ranked.scored;
    longs = ranked.longs;
    shorts = ranked.shorts;
    ton = rows.find((r) => r.coin === FOCUS) || null;
    updatedAt = ts;
    st = 'ready';
  }

  let snapAt = 0;
  async function loadSnap() {
    // raw.githubusercontent кэшируется ~5 мин, файл обновляется раз в час —
    // перечитываем не чаще раза в 10 минут, чтобы открытая вкладка не застывала.
    if (!snap || Date.now() - snapAt > 600e3) {
      snap = await fetch(MARKETS_URL).then((r) => (r.ok ? r.json() : null));
      snapAt = Date.now();
    }
    return snap;
  }

  async function refresh() {
    if (busy) return;
    busy = true;
    try {
      const [meta, ctxs] = await info({ type: 'metaAndAssetCtxs' });
      live = true;
      apply(meta, ctxs, Date.now());
    } catch (e) {
      try {
        const d = await loadSnap();
        if (!d?.meta || !d?.ctxs) throw e;
        live = false;
        apply(d.meta, d.ctxs, d.updated);
      } catch {
        if (st !== 'ready') { err = String(e.message || e); st = 'error'; }
      }
    }
    busy = false;
  }

  async function loadSpark() {
    try {
      const end = Date.now();
      const c = await info({ type: 'candleSnapshot',
        req: { coin: FOCUS, interval: '1h', startTime: end - 7 * 86400e3, endTime: end } });
      spark = sparkPoints((c || []).map((k) => parseFloat(k.c)), 220, 48);
    } catch {
      // живое API недоступно — свечи фокуса из того же снапшота воркера
      try { spark = sparkPoints((await loadSnap())?.candles?.[FOCUS] || [], 220, 48); }
      catch { /* спарклайн опционален */ }
    }
  }

  onMount(() => {
    refresh().then(loadSpark);
    const iv = setInterval(() => { if (!document.hidden) refresh(); }, 60000);
    const onVis = () => { if (!document.hidden) refresh(); };
    document.addEventListener('visibilitychange', onVis);
    return () => { clearInterval(iv); document.removeEventListener('visibilitychange', onVis); };
  });

  const chgCls = (v) => (v > 0 ? 'good' : v < 0 ? 'bad' : '');
  const biasCls = (s) => (s === 'long' ? 'good' : s === 'short' ? 'bad' : 'muted');
  const biasTxt = { long: 'LONG', short: 'SHORT', flat: '—' };
</script>

<svelte:head><title>Perps — TON Quant</title></svelte:head>

<header class="hd">
  <div class="hd-top"><h1>Perps</h1>
    <span class="muted">перпетуалы Hyperliquid · фандинг, OI, моментум → эвристический bias · live 60s</span>
    {#if updatedAt}<span class="muted upd">обновлено {new Date(updatedAt).toLocaleTimeString()}</span>{/if}
    {#if st === 'ready' && !live}<span class="upd warn">API Hyperliquid недоступен из вашей сети (гео-блокировка) — снапшот воркера, обновляется раз в час</span>{/if}
  </div>
</header>

{#if st === 'loading'}<div class="muted pad">Загружаю рынки Hyperliquid…</div>
{:else if st === 'error'}<div class="card bad">Ошибка: {err}</div>
{:else}
  <!-- TON featured -->
  <section class="card tonc">
    <div class="sec-title">GRAM-PERP <span class="muted">· Toncoin (экс-TON, делистнут 21.06.2026) · фокус страницы · Hyperliquid</span></div>
    {#if !ton}
      <p class="muted sm">GRAM-перп сейчас не проходит фильтр ликвидности ($1M/24ч) или не листингован.</p>
    {:else}
      <div class="feat">
        <div class="fst">
          <span class="fv mono">{fmtUsd(ton.mark)}</span>
          <span class="fl mono {chgCls(ton.chg24)}">{fmtPct(ton.chg24, 2)} · 24ч</span>
        </div>
        <div class="fgrid">
          <div><span class="kl">Funding APR</span><span class="kv mono {chgCls(-ton.fundApr)}">{fmtPct(ton.fundApr, 1)}</span></div>
          <div><span class="kl">Open interest</span><span class="kv mono">{fmtUsd(ton.oiUsd)}</span></div>
          <div><span class="kl">Volume 24h</span><span class="kv mono">{fmtUsd(ton.volUsd)}</span></div>
          <div><span class="kl">Bias</span><span class="kv {biasCls(signalLabel(ton.sig.score))}">{biasTxt[signalLabel(ton.sig.score)]} <span class="mono">{ton.sig.score.toFixed(0)}</span></span></div>
        </div>
        {#if spark}
          <svg viewBox="0 0 220 48" class="spark" preserveAspectRatio="none">
            <polyline points={spark} fill="none" stroke="var(--accent)" stroke-width="1.5" />
          </svg>
          <span class="muted sm">7 дней · 1h close</span>
        {/if}
      </div>
    {/if}
  </section>

  <!-- Signals -->
  <div class="cols">
    <section class="card">
      <div class="sec-title good">Long-кандидаты <span class="muted">· score ≥ 25</span></div>
      {#if !longs.length}<p class="muted sm">Нет уверенных long-сетапов прямо сейчас.</p>
      {:else}
        {#each longs as r}
          <div class="sig">
            <span class="sym">{r.coin}</span>
            <span class="mono muted">{fmtUsd(r.mark)}</span>
            <span class="chips">
              <span class="chip {chgCls(r.chg24)}">{fmtPct(r.chg24, 1)} 24ч</span>
              <span class="chip">{fmtPct(r.fundApr, 0)} fund</span>
            </span>
            <span class="score mono good">+{r.sig.score.toFixed(0)}</span>
          </div>
        {/each}
      {/if}
    </section>
    <section class="card">
      <div class="sec-title bad">Short-кандидаты <span class="muted">· score ≤ −25</span></div>
      {#if !shorts.length}<p class="muted sm">Нет уверенных short-сетапов прямо сейчас.</p>
      {:else}
        {#each shorts as r}
          <div class="sig">
            <span class="sym">{r.coin}</span>
            <span class="mono muted">{fmtUsd(r.mark)}</span>
            <span class="chips">
              <span class="chip {chgCls(r.chg24)}">{fmtPct(r.chg24, 1)} 24ч</span>
              <span class="chip">{fmtPct(r.fundApr, 0)} fund</span>
            </span>
            <span class="score mono bad">{r.sig.score.toFixed(0)}</span>
          </div>
        {/each}
      {/if}
    </section>
  </div>

  <!-- Full table -->
  <section class="card tw">
    <div class="sec-title">Все рынки <span class="muted">· ≥$1M объёма за 24ч · сортировка по объёму</span></div>
    <table>
      <thead><tr><th>Coin</th><th class="r">Mark</th><th class="r">24ч</th><th class="r">Funding APR</th>
        <th class="r">OI</th><th class="r">Vol 24h</th><th class="r">Premium</th><th class="r">Score</th><th class="r">Bias</th></tr></thead>
      <tbody>
        {#each rows as r}
          <tr class:focus={r.coin === FOCUS}>
            <td><span class="sym">{r.coin}</span> {#if r.maxLev}<span class="muted lev">{r.maxLev}x</span>{/if}</td>
            <td class="r mono">{fmtUsd(r.mark)}</td>
            <td class="r mono {chgCls(r.chg24)}">{fmtPct(r.chg24, 2)}</td>
            <td class="r mono {chgCls(-r.fundApr)}">{fmtPct(r.fundApr, 1)}</td>
            <td class="r mono">{fmtUsd(r.oiUsd)}</td>
            <td class="r mono">{fmtUsd(r.volUsd)}</td>
            <td class="r mono">{fmtPct(r.premium, 3)}</td>
            <td class="r mono">{r.sig.score.toFixed(0)}</td>
            <td class="r {biasCls(signalLabel(r.sig.score))}">{biasTxt[signalLabel(r.sig.score)]}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>

  <p class="muted foot">Данные — публичный info-API Hyperliquid (mark, prevDay, funding, OI, объём, premium),
    без ключей, прямо из браузера. Score = 45% моментум 24ч + 35% контр-фандинг (перегретые лонги платят
    положительный фандинг → тилт в шорт) + 20% mark-oracle premium; насыщение на ±100. Это наши эвристики.
    Сигналы TG-каналов (@perptools_ai_bot, @dexnewtoken) — на странице TG Sig.
    Funding APR = часовая ставка × 24 × 365. Не финансовый совет.</p>
{/if}

<style>
  .hd{margin-bottom:16px}.hd-top{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}h1{font-size:24px}
  .upd{font-size:12px}.warn{color:var(--bad)}.pad{padding:30px 0}section{margin-bottom:16px}
  .sm{font-size:13px;line-height:1.5}
  .sec-title{display:flex;align-items:baseline;gap:8px;margin-bottom:10px}
  .tonc{border-color:rgba(34,167,255,.35)}
  .feat{display:flex;flex-direction:column;gap:10px}
  .fst{display:flex;align-items:baseline;gap:12px}
  .fv{font-size:26px;font-weight:700}
  .fl{font-size:14px;font-weight:600}
  .fgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}
  .kl{display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
  .kv{font-size:15px;font-weight:600}
  .spark{width:100%;max-width:460px;height:48px}
  .cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  .sig{display:flex;align-items:center;gap:10px;padding:7px 0;border-top:1px solid var(--border)}
  .sig:first-of-type{border-top:none}
  .chips{display:flex;gap:6px;margin-left:auto}
  .chip{font-size:11px;padding:2px 7px;border-radius:99px;background:var(--card);border:1px solid var(--border);white-space:nowrap}
  .score{font-weight:700;min-width:36px;text-align:right}
  table{width:100%;border-collapse:collapse;font-size:13px}.tw{overflow-x:auto}
  th{color:var(--dim);font-weight:400;text-align:left;padding:6px 9px;font-size:11px;white-space:nowrap}
  td{padding:8px 9px;border-top:1px solid var(--border);white-space:nowrap}
  .r{text-align:right}.sym{font-weight:500}.lev{font-size:11px}
  tr.focus td{background:rgba(34,167,255,.07)}
  .good{color:var(--good)}.bad{color:var(--bad)}
  .foot{font-size:11px;margin-top:14px;line-height:1.6;max-width:720px}
  @media(max-width:700px){.cols{grid-template-columns:1fr}}
</style>
