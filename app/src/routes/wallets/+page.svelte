<script>
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { loadWallets, loadDeskStatus } from '$lib/data.js';
  import { walletHref } from '$lib/wallets.js';

  let st = $state('loading');
  let data = $state(null);
  let verdicts = $state(null); // null until loaded / absent -> page degrades gracefully (no risk layer)
  let sort = $state('smart'); // combined who-to-copy rank (default); 'edge'=skill, 'breadth'=conviction

  const short = (a) => a.slice(0, 4) + '…' + a.slice(-4);
  const fmtEdge = (e) => (e == null ? '—' : (e > 0 ? '+' : '') + e + '%');

  let vByAddr = $derived.by(() => {
    const m = new Map();
    for (const w of verdicts?.wallets || []) m.set(w.addr, w);
    return m;
  });
  let riskBySym = $derived.by(() => {
    const m = new Map();
    for (const t of verdicts?.tokens || []) m.set(t.sym, t);
    return m;
  });

  let roster = $derived.by(() => {
    const byMetric = (a, b) =>
      sort === 'smart'
        ? (b.smart ?? -1e9) - (a.smart ?? -1e9) || b.n - a.n
        : sort === 'edge'
          ? (b.edge ?? -1e9) - (a.edge ?? -1e9) || b.n - a.n
          : sort === 'win'
            ? (b.win ?? -1) - (a.win ?? -1) || (b.edge ?? -1e9) - (a.edge ?? -1e9)
            : sort === 'conv'
              ? (b.conv ?? -1) - (a.conv ?? -1) || b.n - a.n
              : b.n - a.n;
    const sorted = [...(data?.roster || [])].sort(byMetric);
    if (!vByAddr.size) return sorted;   // no desk verdicts -> plain sort, no risk layer
    // desk-vetted: copy_ok wallets float to the top, flagged (copy_ok=false) sink to
    // the bottom; wallets the desk hasn't scored (yet) stay in the middle, untouched.
    const bucket = (w) => { const v = vByAddr.get(w.addr); return v ? (v.copy_ok ? 0 : 2) : 1; };
    return sorted
      .map((w, i) => ({ w, i }))
      .sort((x, y) => bucket(x.w) - bucket(y.w) || x.i - y.i)
      .map(({ w }) => w);
  });
  let signals = $derived(roster.filter((w) => w.new && w.new.length));

  onMount(async () => {
    try {
      data = await loadWallets();
      st = data && data.roster?.length ? 'ready' : 'empty';
    } catch (e) {
      st = 'error';
    }
    loadDeskStatus().then((v) => (verdicts = v)).catch(() => {});
  });
</script>

<svelte:head><title>TON Quant — Smart money</title></svelte:head>

<header class="hd">
  <div class="hd-top"><h1>Smart money</h1>
    <span class="muted">кошельки, входящие в топ-холдеры сразу нескольких отслеживаемых токенов — следи за тем, что они покупают</span>
  </div>
  {#if data}
    <div class="legend muted">скан {data.scanned} токенов · {data.wallets} кошельков · ростер {data.roster_size} · {data.date}</div>
  {/if}
  {#if st === 'ready'}
    <div class="sortbar">
      <span class="muted small">сортировка:</span>
      <button class="sb" class:on={sort === 'smart'} onclick={() => (sort = 'smart')}>по smart-score</button>
      <button class="sb" class:on={sort === 'edge'} onclick={() => (sort = 'edge')}>по edge ({data.edge_days || 7}д)</button>
      <button class="sb" class:on={sort === 'win'} onclick={() => (sort = 'win')}>по hit-rate</button>
      <button class="sb" class:on={sort === 'conv'} onclick={() => (sort = 'conv')}>по conviction</button>
      <button class="sb" class:on={sort === 'breadth'} onclick={() => (sort = 'breadth')}>по breadth</button>
    </div>
  {/if}
</header>

{#if st === 'loading'}<div class="muted pad">Загружаю ростер…</div>
{:else if st === 'error'}<div class="card bad">Не удалось загрузить data/wallets.json</div>
{:else if st === 'empty'}<div class="muted pad">Данных пока нет — первый прогон скрипта в ожидании.</div>
{:else}
  {#if signals.length}
    <section class="card sig">
      <div class="sig-h"><i class="ti ti-bolt"></i> Новые входы со вчера ({signals.reduce((s, w) => s + w.new.length, 0)})</div>
      <div class="muted small">эти кошельки сегодня впервые попали в топ-холдеры новых токенов — кандидаты на copy-buy</div>
      {#each signals as w}
        <div class="sig-row">
          <a class="addr mono" href={walletHref(base, w.addr)} title={w.addr}>{w.name || short(w.addr)}</a>
          <span class="chips">{#each w.new as t}<span class="chip new">{t}</span>{/each}</span>
        </div>
      {/each}
    </section>
  {/if}

  {#if data.favorites?.length}
    <section class="card fav">
      <div class="fav-h"><i class="ti ti-flame"></i> Топ токенов у умных денег</div>
      <div class="muted small">консенсус «умных денег» по экосистеме: <b>⚖cons</b> = rank-взвешенное число держателей ростера (топ-холдер весит больше хвоста), <b>N×</b> = сырое число держателей. edge = средняя {data.edge_days || 7}-дн. доходность этих держателей</div>
      {#each data.favorites.slice(0, 15) as f}
        {@const tokV = riskBySym.get(f.sym)}
        <div class="fav-row">
          <span class="chip fav-tok">{f.sym}</span>
          <span class="fav-bar"><span class="fav-fill" style="width:{((f.cons ?? f.holders) / (data.favorites[0].cons ?? data.favorites[0].holders)) * 100}%"></span></span>
          {#if f.cons != null}<span class="conv mono" title="rank-взвешенный консенсус: Σ (26−rank)/25 по держателям ростера — токен, где умные деньги топ-холдеры, бьёт тот, что держат лишь хвостом">⚖{f.cons}</span>{/if}
          <span class="fav-n mono" title="сырое число держателей ростера">{f.holders}×</span>
          {#if f.avg_edge != null}<span class="edge mono" class:up={f.avg_edge > 0} class:down={f.avg_edge < 0}>{fmtEdge(f.avg_edge)}</span>{/if}
          {#if f.new}<span class="chip new">+{f.new}</span>{/if}
          {#if tokV?.manip_risk === 'high'}<span class="risk high" title="AI Desk: {tokV.reason || 'высокий риск манипуляции'}">⚠ risk</span>{/if}
        </div>
      {/each}
    </section>
  {/if}

  <div class="grid">
    {#each roster as w, i}
      {@const v = vByAddr.get(w.addr)}
      <div class="card wc" class:dirty={v && !v.copy_ok}>
        <div class="wc-top">
          <span class="rank mono">#{i + 1}</span>
          <a class="addr mono" href={walletHref(base, w.addr)} title={w.addr}>{w.name || short(w.addr)}</a>
          {#if v}
            <span class="risk {v.manip_risk}" title="AI Desk vetting{v.copy_ok ? ' — можно копировать' : ' — не копировать'} (conviction {v.conviction}): {v.reason}">{v.manip_risk}</span>
          {/if}
          {#if w.smart != null}
            <span class="smart mono" class:up={w.smart > 0} class:down={w.smart < 0}
              title="smart-score — единый рейтинг «кого копировать»: shrunk edge × hit-rate × breadth-бонус (edge·ne/(ne+3)·win/100·(1+0.1·(n−2))). Тонкая выборка и непостоянство тянут вниз; отрицательный edge → отрицательный скор">★{w.smart}</span>
          {/if}
          {#if w.edge != null}
            <span class="edge mono" class:up={w.edge > 0} class:down={w.edge < 0}
              title="средняя доходность отслеживаемых токенов в портфеле за {data.edge_days || 7}д (на основе {w.ne} цен) — прокси скилла отбора">{fmtEdge(w.edge)}</span>
          {/if}
          {#if w.win != null}
            <span class="win mono" class:up={w.win >= 50} class:down={w.win < 50}
              title="доля отслеживаемых токенов в портфеле, выросших за {data.edge_days || 7}д (из {w.ne} с ценой) — консистентность отбора, в отличие от edge один памп её не вытягивает">{w.win}%↑</span>
          {/if}
          {#if w.conv != null}
            <span class="conv mono"
              title="conviction — rank-взвешенная breadth: топ-холдер (rank 1) весит ~1.0, хвост (rank 25) ~0.04. Два кошелька в одном числе токенов различаются резко, если один — КРУПНЕЙШИЙ холдер каждого, а другой едва в топ-25">⚖{w.conv}</span>
          {/if}
          <span class="n" title="в скольких отслеживаемых токенах — топ-холдер">{w.n}×</span>
        </div>
        <div class="chips">
          {#each w.toks as t}<span class="chip" class:new={w.new?.includes(t)}>{t}</span>{/each}
        </div>
      </div>
    {/each}
  </div>
  <p class="muted small foot"><b>smart-score</b> (сортировка по умолчанию) = единый рейтинг «кого копировать»: edge, ужатый по размеру выборки (ne/(ne+3) — один лаки-хит на 1 токене сжимается сильно), × hit-rate (систематичность) × бонус за breadth — сводит три метрики в одно число. <b>edge</b> = средняя {data.edge_days || 7}-дн. доходность отслеживаемых токенов в портфеле кошелька (прокси скилла отбора по результату, не entry-PnL): отделяет тех, кто реально набирает растущие токены, от бэгхолдеров. <b>hit-rate</b> = доля отслеживаемых токенов в портфеле, выросших за окно (из тех, что с ценой): консистентность отбора — edge +35% может быть одним пампом, hit-rate показывает, систематический ли это скилл. <b>breadth</b> = число отслеживаемых токенов, где кошелёк в топ-{25} холдеров (CEX/DEX/пулы/скам отфильтрованы) — «whale-конвикшн по экосистеме». <b>conviction</b> (⚖) = та же breadth, но rank-взвешенная: вклад токена = (26−rank)/25, так что быть КРУПНЕЙШИМ холдером весит ~1.0, а едва в топ-25 — ~0.04. Отделяет кита, реально доминирующего в позициях, от того, кто лишь формально в списке. Самый чистый copy-сигнал — раздел «новые входы» (наполняется со второго дня).</p>
{/if}

<style>
  .hd{margin-bottom:16px}
  .hd-top{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
  h1{font-family:var(--head);font-size:22px;margin:0}
  .legend{margin-top:6px;font-size:12px}
  .small{font-size:12px}
  .pad{padding:20px 0}
  .card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 14px}
  .bad{color:#ff6b6b}
  .sig{margin-bottom:16px;border-color:rgba(34,167,255,.4);background:rgba(34,167,255,.06)}
  .sig-h{font-family:var(--head);font-size:14px;color:var(--accent);display:flex;align-items:center;gap:6px}
  .sig-row{display:flex;gap:10px;align-items:center;margin-top:8px;flex-wrap:wrap}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(248px,1fr));gap:10px}
  .wc-top{display:flex;align-items:center;gap:8px;margin-bottom:8px}
  .rank{color:var(--muted);font-size:12px}
  .addr{color:var(--accent);font-size:13px;text-decoration:none;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .addr:hover{text-decoration:underline}
  .n{font-size:12px;color:var(--text);background:rgba(255,255,255,.06);border-radius:6px;padding:1px 7px}
  .conv{font-size:12px;color:#c9a8ff;background:rgba(167,139,250,.14);border-radius:6px;padding:1px 7px}
  .smart{font-size:12px;font-weight:600;color:var(--muted);background:rgba(255,255,255,.06);border-radius:6px;padding:1px 7px}
  .smart.up{color:#41d68a;background:rgba(65,214,138,.14)}
  .smart.down{color:#ff6b6b;background:rgba(255,107,107,.12)}
  .edge{font-size:12px;color:var(--muted);background:rgba(255,255,255,.06);border-radius:6px;padding:1px 7px}
  .edge.up{color:#41d68a;background:rgba(65,214,138,.12)}
  .edge.down{color:#ff6b6b;background:rgba(255,107,107,.12)}
  .win{font-size:12px;color:var(--muted);background:rgba(255,255,255,.06);border-radius:6px;padding:1px 7px}
  .win.up{color:#41d68a;background:rgba(65,214,138,.12)}
  .win.down{color:#ffae57;background:rgba(255,174,87,.12)}
  .risk{font-size:11px;font-weight:600;text-transform:uppercase;border-radius:6px;padding:1px 7px;cursor:help}
  .risk.low{color:#41d68a;background:rgba(65,214,138,.12)}
  .risk.med{color:#ffae57;background:rgba(255,174,87,.12)}
  .risk.high{color:#ff6b6b;background:rgba(255,107,107,.16)}
  .wc.dirty{opacity:.55}
  .wc.dirty:hover{opacity:.9}
  .sortbar{display:flex;align-items:center;gap:8px;margin-top:10px}
  .sb{font-size:12px;color:var(--muted);background:var(--card);border:1px solid var(--border);border-radius:8px;padding:3px 10px;cursor:pointer}
  .sb.on{color:var(--accent);border-color:rgba(34,167,255,.5);background:rgba(34,167,255,.08)}
  .chips{display:flex;flex-wrap:wrap;gap:4px}
  .chip{font-size:11px;padding:2px 7px;border-radius:6px;background:rgba(255,255,255,.05);color:var(--muted)}
  .chip.new{background:rgba(34,167,255,.18);color:var(--accent)}
  .mono{font-family:ui-monospace,Menlo,Consolas,monospace}
  .foot{margin-top:16px;max-width:680px;line-height:1.5}
  .fav{margin-bottom:16px}
  .fav-h{font-family:var(--head);font-size:14px;display:flex;align-items:center;gap:6px;margin-bottom:2px}
  .fav-row{display:flex;align-items:center;gap:8px;margin-top:7px}
  .fav-tok{flex:0 0 90px;text-align:center;color:var(--text);background:rgba(255,255,255,.06)}
  .fav-bar{flex:1;height:7px;border-radius:4px;background:rgba(255,255,255,.05);overflow:hidden}
  .fav-fill{display:block;height:100%;background:var(--accent);opacity:.55;border-radius:4px}
  .fav-n{font-size:12px;color:var(--text);min-width:30px;text-align:right}
</style>
