<script>
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { loadAll } from '$lib/data.js';
  import { arbView } from '$lib/arb.js';
  import { fmtUsd, fmtPct } from '$lib/format.js';

  // GRAM (GRM) — постоянный фокус страницы
  const GRAM = 'EQC47093oX5Xhb0xuk2lCr2RhS8rj-vul61u4W2UH5ORmG_O';
  const CANDIDATES = 8; // ponytail: DexScreener — 1 запрос на токен; топ-N по дневному спреду + GRAM

  let st = $state('loading');
  let err = $state('');
  let gram = $state(null);
  let opps = $state([]);
  let scannedAt = $state(null);
  let scanning = $state(false);
  let watch = [];

  const dexJ = (addr) =>
    fetch(`https://api.dexscreener.com/latest/dex/tokens/${addr}`)
      .then((r) => (r.ok ? r.json() : null)).catch(() => null);

  async function scan() {
    if (scanning || !watch.length) return;
    scanning = true;
    const res = await Promise.all(watch.map(async (w) => {
      const d = await dexJ(w.addr);
      const v = d ? arbView(d.pairs, w.addr) : null;
      return v ? { ...w, ...v } : null;
    }));
    const got = res.filter(Boolean);
    gram = got.find((x) => x.addr === GRAM) || gram;
    opps = got.filter((x) => x.addr !== GRAM).sort((a, b) => b.net.netUsd - a.net.netUsd);
    scannedAt = Date.now();
    scanning = false;
  }

  onMount(() => {
    (async () => {
      try {
        const d = await loadAll();
        // кандидаты: дневной межпуловый спред из снапшота (Track B) + просто мульти-пуловые
        const ranked = d.rows
          .map((r) => ({ addr: r.addr, sym: r.sym, daySpread: r.hist?.[r.hist.length - 1]?.spread ?? null, pools: r.pools || 0 }))
          .filter((r) => r.addr !== GRAM && (r.daySpread != null ? r.daySpread > 0.3 : r.pools > 1))
          .sort((a, b) => (b.daySpread ?? 0) - (a.daySpread ?? 0) || b.pools - a.pools)
          .slice(0, CANDIDATES - 1);
        const gramRow = d.rows.find((r) => r.addr === GRAM);
        watch = [{ addr: GRAM, sym: gramRow?.sym || 'GRAM', daySpread: gramRow?.hist?.[gramRow.hist.length - 1]?.spread ?? null }, ...ranked];
        await scan();
        st = 'ready';
      } catch (e) { err = String(e.message || e); st = 'error'; }
    })();
    const iv = setInterval(() => { if (!document.hidden) scan(); }, 60000);
    const onVis = () => { if (!document.hidden) scan(); };
    document.addEventListener('visibilitychange', onVis);
    return () => { clearInterval(iv); document.removeEventListener('visibilitychange', onVis); };
  });

  const netCls = (v) => (v > 0 ? 'good' : v < 0 ? 'bad' : '');
</script>

<svelte:head><title>Arbitrage — TON Quant</title></svelte:head>

<header class="hd">
  <div class="hd-top"><h1>Arbitrage</h1>
    <span class="muted">межпуловый спред на TON DEX · нетто после комиссий (2×0.3%) и газа · live 60s</span>
    {#if scannedAt}<span class="muted upd">скан {new Date(scannedAt).toLocaleTimeString()}</span>{/if}
  </div>
</header>

{#if st === 'loading'}<div class="muted pad">Сканирую пулы…</div>
{:else if st === 'error'}<div class="card bad">Ошибка: {err}</div>
{:else}
  <!-- GRAM featured -->
  <section class="card gramc">
    <div class="sec-title">GRAM <span class="muted">· {gram?.sym || 'GRM'} · фокус страницы</span>
      <a class="tlink" href="{base}/token?a={GRAM}">страница токена →</a></div>
    {#if !gram}
      <p class="muted sm">Меньше двух ликвидных пулов у GRAM прямо сейчас — арбитражить нечего. Скан продолжается каждые 60с.</p>
    {:else}
      <div class="duel">
        <div class="side">
          <span class="sl">купить · {gram.buy.dex}</span>
          <span class="sv mono">{fmtUsd(gram.buy.price)}</span>
          <span class="sn muted">{gram.buy.pair} · liq {fmtUsd(gram.buy.liq)}</span>
        </div>
        <div class="mid">
          <span class="gs mono">{gram.pct.toFixed(2)}%</span>
          <span class="muted sm">gross спред</span>
          <span class="net mono {netCls(gram.net.netUsd)}">{gram.net.netUsd > 0 ? '+' : ''}{fmtUsd(gram.net.netUsd)} нетто</span>
          {#if gram.net.size > 0}<span class="muted sm">опт. размер {fmtUsd(gram.net.size)}</span>{/if}
        </div>
        <div class="side">
          <span class="sl">продать · {gram.sell.dex}</span>
          <span class="sv mono">{fmtUsd(gram.sell.price)}</span>
          <span class="sn muted">{gram.sell.pair} · liq {fmtUsd(gram.sell.liq)}</span>
        </div>
      </div>
      <table class="pt">
        <thead><tr><th>Пул</th><th class="r">Цена</th><th class="r">Liquidity</th><th class="r">Vol 24h</th><th class="r">vs min</th></tr></thead>
        <tbody>
          {#each gram.pools as p}
            <tr><td>{p.dex} <span class="muted">{p.pair}</span></td>
              <td class="r mono">{fmtUsd(p.price)}</td><td class="r mono">{fmtUsd(p.liq)}</td>
              <td class="r mono">{fmtUsd(p.vol)}</td>
              <td class="r mono" class:warn={(p.price / gram.buy.price - 1) * 100 > 1}>{fmtPct((p.price / gram.buy.price - 1) * 100, 2)}</td></tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>

  <!-- Opportunities -->
  <section class="card tw">
    <div class="sec-title">Возможности <span class="muted">· топ по дневному спреду из снапшота, пересканировано live</span></div>
    {#if !opps.length}
      <p class="muted sm">Сейчас нет токенов с ≥2 ликвидными пулами среди кандидатов — рынок сшит плотно. Дневной спред-скрин обновится со следующим снапшотом.</p>
    {:else}
      <table>
        <thead><tr><th>Jetton</th><th>Купить</th><th>Продать</th><th class="r">Gross</th><th class="r">Нетто $</th><th class="r">Нетто %</th><th class="r">Размер</th></tr></thead>
        <tbody>
          {#each opps as o}
            <tr>
              <td><a href="{base}/token?a={o.addr}"><span class="sym">{o.sym}</span></a></td>
              <td class="muted">{o.buy.dex} <span class="mono">{fmtUsd(o.buy.price)}</span></td>
              <td class="muted">{o.sell.dex} <span class="mono">{fmtUsd(o.sell.price)}</span></td>
              <td class="r mono">{o.pct.toFixed(2)}%</td>
              <td class="r mono {netCls(o.net.netUsd)}">{o.net.netUsd > 0 ? '+' : ''}{fmtUsd(o.net.netUsd)}</td>
              <td class="r mono {netCls(o.net.netPct)}">{fmtPct(o.net.netPct, 2)}</td>
              <td class="r mono">{o.net.size > 0 ? fmtUsd(o.net.size) : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>

  <p class="muted foot">Нетто = спред − слиппедж обеих ног (CPMM, s/y на ногу) − комиссии DEX 2×0.3% − газ ~$0.15,
    размер подбирается сканом до 50% меньшего полурезерва. Положительное нетто — редкое и короткоживущее:
    исполнение не атомарно (две транзакции), цена может уйти между ногами. Кандидаты — из дневного
    межпулового спреда снапшота (Track B), GRAM закреплён всегда. Не финансовый совет.</p>
{/if}

<style>
  .hd{margin-bottom:16px}.hd-top{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}h1{font-size:24px}
  .upd{font-size:12px}.pad{padding:30px 0}section{margin-bottom:16px}
  .sm{font-size:13px;line-height:1.5}
  .tlink{margin-left:auto;font-size:12px;color:var(--accent);font-weight:400}
  .sec-title{display:flex;align-items:baseline;gap:8px}
  .gramc{border-color:rgba(34,167,255,.35)}
  .duel{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:14px;margin:12px 0 14px}
  .side{display:flex;flex-direction:column;gap:3px;text-align:center}
  .sl{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
  .sv{font-size:22px;font-weight:600}
  .sn{font-size:11px}
  .mid{display:flex;flex-direction:column;gap:2px;text-align:center}
  .gs{font-size:26px;font-weight:700}
  .net{font-size:13px;font-weight:600}
  .pt{margin-top:4px}
  table{width:100%;border-collapse:collapse;font-size:13px}.tw{overflow-x:auto}
  th{color:var(--dim);font-weight:400;text-align:left;padding:6px 9px;font-size:11px;white-space:nowrap}
  td{padding:8px 9px;border-top:1px solid var(--border);white-space:nowrap}
  .r{text-align:right}.sym{font-weight:500}
  .good{color:var(--good)}.bad{color:var(--bad)}.warn{color:var(--warn)}
  .foot{font-size:11px;margin-top:14px;line-height:1.6;max-width:720px}
  @media(max-width:560px){.duel{grid-template-columns:1fr;gap:8px}}
</style>
