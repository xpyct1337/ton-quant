<script>
  import { onMount } from 'svelte';
  import { fmtUsd, fmtPct } from '$lib/format.js';
  import { perpRows, rankSignals, signalLabel, sparkPoints } from '$lib/perps.js';

  // Hyperliquid public info API: без ключа, CORS открыт, POST-запросы.
  // ponytail: 2 запроса на обновление (метаданные+контексты всех перпов одним
  // вызовом, свечи только для GRAM (ex-TON)) — сигналы закрытого @perptools_ai_bot
  // недоступны, считаем свои эвристики на тех же рыночных данных.
  const HL = 'https://api.hyperliquid.xyz/info';
  const FOCUS = 'GRAM'; // TON rebranded to GRAM on Hyperliquid
  // Собранные коллектором сигналы @perptools_ai_bot (scripts/perp_signals.py,
  // перезаливается воркфлоу perp-signals.yml). Файла нет → секция скрыта.
  const SIGNALS_URL = 'https://raw.githubusercontent.com/xpyct1337/ton-quant/main/data/perp_signals.json';

  let st = $state('loading');
  let err = $state('');
  let rows = $state([]);
  let longs = $state([]);
  let shorts = $state([]);
  let ton = $state(null);
  let spark = $state('');
  let updatedAt = $state(null);
  let bot = $state(null);
  let botFilter = $state('all');
  let botShowRaw = $state({});
  let busy = false;

  const ago = (ts) => {
    const d = Math.floor((Date.now() / 1000 - ts) / 60);
    if (d < 60) return d + 'м';
    if (d < 1440) return Math.floor(d / 60) + 'ч';
    return Math.floor(d / 1440) + 'д';
  };
  const fmtPrice = (p) => p == null ? null : p >= 1000 ? p.toFixed(0) : p >= 1 ? p.toFixed(3) : p.toFixed(6);
  const fmtTs = (ts) => new Date(ts * 1000).toLocaleString('ru', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

  const info = (body) =>
    fetch(HL, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then((r) => { if (!r.ok) throw new Error('Hyperliquid HTTP ' + r.status); return r.json(); });

  async function refresh() {
    if (busy) return;
    busy = true;
    try {
      const [meta, ctxs] = await info({ type: 'metaAndAssetCtxs' });
      const all = perpRows(meta, ctxs);
      const ranked = rankSignals(all, 5);
      rows = ranked.scored;
      longs = ranked.longs;
      shorts = ranked.shorts;
      ton = rows.find((r) => r.coin === FOCUS) || null;
      updatedAt = Date.now();
      st = 'ready';
    } catch (e) {
      if (st !== 'ready') { err = String(e.message || e); st = 'error'; }
    }
    busy = false;
  }

  async function loadSpark() {
    try {
      const end = Date.now();
      const c = await info({ type: 'candleSnapshot',
        req: { coin: FOCUS, interval: '1h', startTime: end - 7 * 86400e3, endTime: end } });
      spark = sparkPoints((c || []).map((k) => parseFloat(k.c)), 220, 48);
    } catch { /* спарклайн опционален */ }
  }

  async function loadBotSignals() {
    try {
      const d = await fetch(SIGNALS_URL).then((r) => (r.ok ? r.json() : null));
      if (d?.signals?.length) bot = d;
    } catch { /* секция опциональна */ }
  }

  onMount(() => {
    refresh().then(loadSpark);
    loadBotSignals();
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
  </div>
</header>

{#if st === 'loading'}<div class="muted pad">Загружаю рынки Hyperliquid…</div>
{:else if st === 'error'}<div class="card bad">Ошибка: {err}</div>
{:else}
  <!-- TON featured -->
  <section class="card tonc">
    <div class="sec-title">GRAM-PERP <span class="muted">· фокус страницы · Hyperliquid</span></div>
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

  <!-- @perptools_ai_bot signals (collector-fed, optional) -->
  {#if bot}
    {@const sigs = bot.signals || []}
    {@const botLongs = sigs.filter((s) => s.side === 'long').length}
    {@const botShorts = sigs.filter((s) => s.side === 'short').length}
    {@const filtered = botFilter === 'all' ? sigs : sigs.filter((s) => s.side === botFilter)}
    <section class="bsec">
      <div class="sec-title">Сигналы @perptools_ai_bot
        <span class="muted sm">· коллектор scripts/perp_signals.py · обновлено {new Date(bot.updated).toLocaleString()}</span>
      </div>

      <div class="bkpis">
        <div class="bkpi"><span class="bkl">всего</span><span class="bkv">{sigs.length}</span></div>
        <div class="bkpi"><span class="bkl">лонги</span><span class="bkv good">{botLongs}</span></div>
        <div class="bkpi"><span class="bkl">шорты</span><span class="bkv bad">{botShorts}</span></div>
        <div class="bkpi"><span class="bkl">обновлено</span><span class="bkv sm mono">{bot.updated?.slice(0,16).replace('T',' ')}</span></div>
      </div>

      <div class="bfilters">
        <button class="bfb" class:act={botFilter === 'all'} onclick={() => botFilter = 'all'}>Все {sigs.length}</button>
        <button class="bfb good" class:act={botFilter === 'long'} onclick={() => botFilter = 'long'}>▲ Long {botLongs}</button>
        <button class="bfb bad" class:act={botFilter === 'short'} onclick={() => botFilter = 'short'}>▼ Short {botShorts}</button>
      </div>

      {#if filtered.length === 0}
        <p class="muted sm">Нет сигналов по фильтру.</p>
      {:else}
        <div class="bgrid">
          {#each filtered as s (s.id)}
            <div class="bcard" class:blong={s.side === 'long'} class:bshort={s.side === 'short'}>
              <div class="bc-top">
                <span class="sym">{s.coin}</span>
                <span class="bside" class:good={s.side === 'long'} class:bad={s.side === 'short'}>
                  {s.side === 'long' ? '▲ LONG' : '▼ SHORT'}
                </span>
                {#if s.lev}<span class="blev">{s.lev}×</span>{/if}
                <span class="muted sm mono ago">{ago(s.ts)}</span>
              </div>

              <div class="levels">
                {#if s.entry != null}
                  <div class="lrow"><span class="ll muted">вход</span><span class="lv mono">{fmtPrice(s.entry)}</span></div>
                {/if}
                {#if s.tps?.length}
                  {#each s.tps as tp, i}
                    <div class="lrow"><span class="ll muted">TP{s.tps.length > 1 ? i+1 : ''}</span><span class="lv mono good">{fmtPrice(tp)}</span></div>
                  {/each}
                {/if}
                {#if s.sl != null}
                  <div class="lrow"><span class="ll muted">SL</span><span class="lv mono bad">{fmtPrice(s.sl)}</span></div>
                {/if}
              </div>

              {#if s.entry && s.sl}
                {@const rr = s.side === 'long'
                  ? ((s.tps?.[0] ?? s.entry) - s.entry) / (s.entry - s.sl)
                  : (s.entry - (s.tps?.[0] ?? s.entry)) / (s.sl - s.entry)}
                {#if isFinite(rr) && rr > 0}
                  <div class="rr muted sm">R:R <span class:good={rr >= 2} class:warn={rr > 0 && rr < 2}>{rr.toFixed(1)}</span></div>
                {/if}
              {/if}

              <div class="bc-foot">
                <span class="muted sm">{fmtTs(s.ts)}</span>
                <button class="raw-btn muted sm" onclick={() => botShowRaw[s.id] = !botShowRaw[s.id]}>
                  {botShowRaw[s.id] ? 'скрыть' : 'raw'}
                </button>
              </div>
              {#if botShowRaw[s.id]}
                <pre class="raw">{s.raw}</pre>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </section>
  {/if}

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
    положительный фандинг → тилт в шорт) + 20% mark-oracle premium; насыщение на ±100. Это наши эвристики,
    а не сигналы @perptools_ai_bot — у бота нет публичного API. Сигналы самого бота (если секция видна)
    собираются коллектором scripts/perp_signals.py из личного чата с ботом через Telethon и парсятся
    best-effort. Funding APR = часовая ставка × 24 × 365. Не финансовый совет.</p>
{/if}

<style>
  .hd{margin-bottom:16px}.hd-top{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}h1{font-size:24px}
  .upd{font-size:12px}.pad{padding:30px 0}section{margin-bottom:16px}
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

  /* bot signals */
  .bsec{margin-bottom:16px}
  .bkpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:8px;margin-bottom:10px}
  .bkpi{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:9px 12px;display:flex;flex-direction:column;gap:2px}
  .bkl{font-size:11px;color:var(--muted)}
  .bkv{font-family:var(--head);font-size:18px;font-weight:600}
  .bkv.sm{font-size:12px}
  .bfilters{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
  .bfb{background:var(--card);border:1px solid var(--border);color:var(--muted);border-radius:8px;
    padding:5px 13px;cursor:pointer;font-size:13px;transition:all .15s}
  .bfb:hover{color:var(--text)}
  .bfb.act{background:rgba(255,255,255,.08);color:var(--text);border-color:rgba(255,255,255,.2)}
  .bfb.good.act{background:rgba(65,214,138,.12);color:var(--good);border-color:rgba(65,214,138,.3)}
  .bfb.bad.act{background:rgba(255,107,107,.12);color:var(--bad);border-color:rgba(255,107,107,.3)}
  .bgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}
  .bcard{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:11px 13px;
    display:flex;flex-direction:column;gap:7px}
  .bcard.blong{border-left:3px solid rgba(65,214,138,.5)}
  .bcard.bshort{border-left:3px solid rgba(255,107,107,.5)}
  .bc-top{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
  .bside{font-size:11px;font-weight:700;padding:2px 6px;border-radius:5px}
  .bside.good{background:rgba(65,214,138,.15)}
  .bside.bad{background:rgba(255,107,107,.14)}
  .blev{font-size:11px;background:rgba(255,255,255,.07);border-radius:5px;padding:2px 6px;color:var(--muted)}
  .ago{margin-left:auto}
  .levels{display:flex;flex-direction:column;gap:3px}
  .lrow{display:flex;justify-content:space-between;align-items:center;font-size:12px}
  .ll{min-width:34px}
  .lv{font-size:13px;font-weight:500}
  .rr{font-size:11px}.rr span{font-weight:600}
  .warn{color:#f0997b}
  .bc-foot{display:flex;justify-content:space-between;align-items:center}
  .raw-btn{background:none;border:none;cursor:pointer;padding:0;font-family:inherit;font-size:11px;color:var(--muted)}
  .raw-btn:hover{color:var(--text)}
  pre.raw{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;color:var(--muted);
    white-space:pre-wrap;word-break:break-word;background:rgba(255,255,255,.03);
    border-radius:6px;padding:8px;margin:0;line-height:1.5}
</style>
