<script>
  import { onMount } from 'svelte';
  import { loadAll, loadSignals, loadDeskStatus, loadDeskCopytrade, loadPaper, loadXsForward, loadPerpSignals } from '$lib/data.js';
  import { fmtUsd, fmtPct, shortAddr } from '$lib/format.js';

  // Дневной срез: то, что изменилось за последние сутки, одним экраном.
  // Всё считается из уже собранных data/*.json — новых запросов к API нет.
  const RAW = 'https://raw.githubusercontent.com/xpyct1337/ton-quant/main/data';
  const j = (u) => fetch(u).then((r) => (r.ok ? r.json() : null)).catch(() => null);

  let st = $state('loading');
  let err = $state('');
  let today = $state('');
  let yesterday = $state('');
  let symOf = {};

  let moversUp = $state([]);
  let moversDown = $state([]);
  let deskNote = $state('');
  let newHighRiskWallets = $state([]);
  let newHighRiskTokens = $state([]);
  let newCopyOk = $state([]);
  let topConviction = $state([]);
  let copytrade = $state(null);
  let bundlers = $state([]);
  let buyerConc = $state([]);
  let socialSpikes = $state([]);
  let paperBots = $state([]);
  let xsLast = $state(null);
  let xsOpen = $state(null);
  let perpFeed = $state([]);

  function pctBot(equity) {
    if (!equity || equity.length < 2) return null;
    const a = equity[equity.length - 2].v, b = equity[equity.length - 1].v;
    return a ? ((b - a) / a) * 100 : null;
  }

  onMount(() => {
    (async () => {
      try {
        const [d, sig, verdicts, ct, paper, xs, perp] = await Promise.all([
          loadAll(), loadSignals(), loadDeskStatus(), loadDeskCopytrade(),
          loadPaper(), loadXsForward(), loadPerpSignals()
        ]);
        symOf = Object.fromEntries(d.rows.map((r) => [r.addr, r.sym]));
        const dates = d.dates;
        today = dates[dates.length - 1];
        yesterday = dates[dates.length - 2] || today;

        const core = d.rows.filter((r) => r.core && r.d1 != null);
        moversUp = [...core].sort((a, b) => b.d1 - a.d1).slice(0, 5);
        moversDown = [...core].sort((a, b) => a.d1 - b.d1).slice(0, 5);

        // Деск: что нового во вчерашних vs сегодняшних вердиктах
        const prevV = await j(`${RAW}/desk/verdicts/${yesterday}.json`);
        const prevW = new Map((prevV?.wallets || []).map((w) => [w.addr, w]));
        const prevT = new Map((prevV?.tokens || []).map((t) => [t.sym, t]));
        const W = verdicts?.wallets || [], T = verdicts?.tokens || [];
        deskNote = verdicts ? `${verdicts.date} · модель ${verdicts.model}` : '';
        newHighRiskWallets = W.filter((w) => w.manip_risk === 'high' && prevW.get(w.addr)?.manip_risk !== 'high');
        newHighRiskTokens = T.filter((t) => t.manip_risk === 'high' && prevT.get(t.sym)?.manip_risk !== 'high');
        newCopyOk = W.filter((w) => w.copy_ok && !prevW.get(w.addr)?.copy_ok);
        topConviction = [...W].filter((w) => w.copy_ok).sort((a, b) => b.conviction - a.conviction).slice(0, 5);
        copytrade = ct;

        // Форензика/потоки/соцсети — сегодня vs вчера
        const [forT, flowT, socT, socY] = await Promise.all([
          j(`${RAW}/forensics/${today}.json`), j(`${RAW}/flows/${today}.json`),
          j(`${RAW}/social/${today}.json`), j(`${RAW}/social/${yesterday}.json`)
        ]);
        bundlers = Object.entries(forT?.tokens || {})
          .map(([addr, f]) => ({ addr, sym: symOf[addr] || shortAddr(addr), ...f }))
          .filter((f) => f.bundle > 0.15).sort((a, b) => b.bundle - a.bundle).slice(0, 5);
        buyerConc = Object.entries(flowT?.tokens || {})
          .map(([addr, f]) => ({ addr, sym: symOf[addr] || shortAddr(addr), ...f }))
          .filter((f) => f.trades_n >= 20 && f.buyer_conc >= 0.6).sort((a, b) => b.buyer_conc - a.buyer_conc).slice(0, 5);
        const socYmap = new Map(Object.entries(socY?.tokens || {}));
        socialSpikes = Object.entries(socT?.tokens || {})
          .map(([addr, s]) => ({ addr, sym: symOf[addr] || shortAddr(addr), mentions: s.mentions, delta: s.mentions - (socYmap.get(addr)?.mentions || 0) }))
          .filter((s) => s.delta > 0).sort((a, b) => b.delta - a.delta).slice(0, 5);

        // Paper-боты и xsmom forward-test
        paperBots = Object.entries(paper.bots || {}).map(([name, b]) => ({
          name, total: b.cash + (b.positions || []).reduce((s, p) => s + p.size, 0),
          d1: pctBot(b.equity), openPositions: (b.positions || []).length
        }));
        xsLast = xs.records?.[xs.records.length - 1] || null;
        xsOpen = xs.state || null;
        perpFeed = (perp?.signals || []).slice(0, 6);

        st = 'ready';
      } catch (e) {
        st = 'error'; err = String(e.message || e);
      }
    })();
  });

  const cls = (v) => (v > 0 ? 'good' : v < 0 ? 'bad' : '');
</script>

<svelte:head><title>Дневной срез — TON Quant</title></svelte:head>

<header class="hd">
  <h1>Дневной срез</h1>
  {#if today}<span class="muted upd">{today}{yesterday && yesterday !== today ? ` · сравнение с ${yesterday}` : ''}</span>{/if}
  <p class="muted lead">Что изменилось за сутки по всем собранным данным — рынок, деск (риск/копи-фид), форензика, соцсети, paper-боты и перпы. Один экран, чтобы не листать все страницы по кругу.</p>
</header>

{#if st === 'loading'}
  <div class="muted pad">Собираю срез…</div>
{:else if st === 'error'}
  <div class="card bad">Не удалось загрузить данные: {err}</div>
{:else}

  <section class="card">
    <div class="sec-title">Рынок за 24ч <span class="muted">· топ-5 роста / падения среди «ядра» (без стейблов и фейк-капов)</span></div>
    <div class="cols2">
      <div>
        <div class="grp-title good">Растут</div>
        {#each moversUp as m}<div class="row"><span class="sym">{m.sym}</span><span class="mono {cls(m.d1)}">{fmtPct(m.d1)}</span></div>{/each}
        {#if !moversUp.length}<p class="muted sm">Нет данных.</p>{/if}
      </div>
      <div>
        <div class="grp-title bad">Падают</div>
        {#each moversDown as m}<div class="row"><span class="sym">{m.sym}</span><span class="mono {cls(m.d1)}">{fmtPct(m.d1)}</span></div>{/each}
        {#if !moversDown.length}<p class="muted sm">Нет данных.</p>{/if}
      </div>
    </div>
  </section>

  <section class="card">
    <div class="sec-title">AI Desk <span class="muted">· {deskNote || 'вердиктов пока нет'}</span></div>
    <p class="muted sm">Деск гоняет LLM-агентов по кошелькам/токенам roster'а и ставит риск манипуляции + флаг «можно копировать». Здесь — что поменялось со вчера.</p>
    {#if !deskNote}
      <p class="muted sm">Деск ещё не писал вердикты — эта секция появится после первого прогона.</p>
    {:else}
      {#if newHighRiskWallets.length}
        <div class="grp-title bad">Новые high-risk кошельки</div>
        {#each newHighRiskWallets as w}<div class="row"><span class="sym">{w.name || shortAddr(w.addr)}</span><span class="muted sm reason">{w.reason}</span></div>{/each}
      {/if}
      {#if newHighRiskTokens.length}
        <div class="grp-title bad">Новые high-risk токены</div>
        {#each newHighRiskTokens as t}<div class="row"><span class="sym">{t.sym}</span><span class="muted sm reason">{t.reason}</span></div>{/each}
      {/if}
      {#if newCopyOk.length}
        <div class="grp-title good">Новые «можно копировать»</div>
        {#each newCopyOk as w}<div class="row"><span class="sym">{w.name || shortAddr(w.addr)}</span><span class="mono">conviction {w.conviction}</span></div>{/each}
      {/if}
      <div class="grp-title">Топ по уверенности деска сегодня</div>
      {#if topConviction.length}
        {#each topConviction as w}<div class="row"><span class="sym">{w.name || shortAddr(w.addr)}</span><span class="mono good">conviction {w.conviction}</span></div>{/each}
      {:else}<p class="muted sm">Сейчас ни один кошелёк не прошёл вёттинг (copy_ok=false у всех) — деск считает roster рискованным.</p>{/if}
      {#if !newHighRiskWallets.length && !newHighRiskTokens.length && !newCopyOk.length}
        <p class="muted sm">Без резких изменений риска со вчерашнего дня.</p>
      {/if}
      {#if copytrade}
        <div class="grp-title">Проверка копи-фида <span class="muted">· окно {copytrade.horizon}д</span></div>
        <p class="muted sm">{copytrade.note} — копирование всех roster-кошельков дало бы {fmtPct(copytrade.copy_all.avg)} в среднем ({copytrade.copy_all.win_rate}% в плюс), деск-фильтр — {fmtPct(copytrade.copy_desk.avg)}.</p>
      {/if}
    {/if}
  </section>

  <section class="card">
    <div class="sec-title">Подозрительная активность <span class="muted">· форензика + потоки сделок, свежий срез</span></div>
    <p class="muted sm">«Bundle» — доля держателей, пришедших одним кластером транзакций (похоже на организованный вход/раздачу). «Buyer conc.» — сколько объёма покупок пришло от небольшого числа адресов (может быть ботами).</p>
    {#if bundlers.length}
      <div class="grp-title bad">Высокий bundle-score</div>
      {#each bundlers as b}<div class="row"><span class="sym">{b.sym}</span><span class="mono bad">bundle {(b.bundle * 100).toFixed(0)}%</span><span class="muted sm">{b.clusters} кластер(ов), макс {b.max_cluster}</span></div>{/each}
    {/if}
    {#if buyerConc.length}
      <div class="grp-title bad">Концентрация покупателей</div>
      {#each buyerConc as f}<div class="row"><span class="sym">{f.sym}</span><span class="mono bad">{(f.buyer_conc * 100).toFixed(0)}% на {f.ubuyers} адресов</span><span class="muted sm">{f.trades_n} сделок</span></div>{/each}
    {/if}
    {#if !bundlers.length && !buyerConc.length}<p class="muted sm">Ничего подозрительного не всплыло на текущем срезе.</p>{/if}
  </section>

  <section class="card">
    <div class="sec-title">Соцсети <span class="muted">· всплески упоминаний $TICKER в отслеживаемых TG-каналах</span></div>
    {#if socialSpikes.length}
      {#each socialSpikes as s}<div class="row"><span class="sym">{s.sym}</span><span class="mono">{s.mentions} упоминаний <span class="good">(+{s.delta})</span></span></div>{/each}
    {:else}<p class="muted sm">Заметных всплесков упоминаний нет.</p>{/if}
  </section>

  <section class="card">
    <div class="sec-title">Paper-боты и momentum forward-test</div>
    {#each paperBots as b}
      <div class="row"><span class="sym">{b.name}</span>
        <span class="mono {cls(b.d1)}">{b.d1 != null ? fmtPct(b.d1) + ' за сутки' : '—'}</span>
        <span class="muted sm">{fmtUsd(b.total)} · {b.openPositions} откр. позиций</span></div>
    {/each}
    {#if xsLast}
      <div class="grp-title">XS-momentum · последняя закрытая ротация</div>
      <div class="row"><span class="mono {cls(xsLast.net)}">{fmtPct(xsLast.net * 100)}</span><span class="muted sm">{xsLast.long.length} long / {xsLast.short.length} short</span></div>
    {/if}
    {#if xsOpen}
      <p class="muted sm">Сейчас открыто: {xsOpen.long?.length || 0} long / {xsOpen.short?.length || 0} short (с {new Date(xsOpen.bar_ts).toISOString().slice(0, 10)}).</p>
    {/if}
    {#if !paperBots.length && !xsLast}<p class="muted sm">Нет данных paper-ботов.</p>{/if}
  </section>

  <section class="card">
    <div class="sec-title">Перп-сигналы <span class="muted">· лента @perptools_ai_bot, последние</span></div>
    {#if perpFeed.length}
      {#each perpFeed as p}<div class="row"><span class="sym">{p.coin}</span><span class="muted sm">{p.kind}{p.pct != null ? ' ' + fmtPct(p.pct) : ''}</span><span class="muted sm">{new Date(p.ts * 1000).toLocaleString()}</span></div>{/each}
    {:else}<p class="muted sm">Сигналов нет (TG-коллектор не настроен или пуст).</p>{/if}
  </section>

  <p class="muted foot">Всё посчитано client-side из уже собранных <code>data/*.json</code> — новых запросов к API нет. Не финансовый совет.</p>
{/if}

<style>
  .hd{margin-bottom:16px}
  h1{font-size:24px;display:inline}
  .upd{font-size:12px;margin-left:10px}
  .lead{max-width:640px;margin-top:8px;font-size:13px;line-height:1.6}
  .pad{padding:30px 0}
  section{margin-bottom:16px}
  .sec-title{display:flex;align-items:baseline;gap:8px;margin-bottom:8px;flex-wrap:wrap}
  .sm{font-size:12px;line-height:1.5}
  .cols2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
  .grp-title{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:12px 0 6px}
  .grp-title:first-of-type{margin-top:0}
  .row{display:flex;align-items:center;gap:10px;padding:6px 0;border-top:1px solid var(--border);flex-wrap:wrap}
  .row:first-of-type{border-top:none}
  .sym{font-weight:500;min-width:64px}
  .reason{flex:1}
  .good{color:var(--good)}.bad{color:var(--bad)}
  .foot{font-size:11px;margin-top:14px;line-height:1.6;max-width:720px}
  code{font-size:11px}
  @media(max-width:700px){.cols2{grid-template-columns:1fr}}
</style>
