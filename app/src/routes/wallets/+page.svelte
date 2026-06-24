<script>
  import { onMount } from 'svelte';
  import { loadWallets } from '$lib/data.js';

  let st = $state('loading');
  let data = $state(null);

  const short = (a) => a.slice(0, 4) + '…' + a.slice(-4);
  const tv = (a) => 'https://tonviewer.com/' + a;

  let roster = $derived(data?.roster || []);
  let signals = $derived(roster.filter((w) => w.new && w.new.length));

  onMount(async () => {
    try {
      data = await loadWallets();
      st = data && data.roster?.length ? 'ready' : 'empty';
    } catch (e) {
      st = 'error';
    }
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
          <a class="addr mono" href={tv(w.addr)} target="_blank" rel="noopener">{w.name || short(w.addr)}</a>
          <span class="chips">{#each w.new as t}<span class="chip new">{t}</span>{/each}</span>
        </div>
      {/each}
    </section>
  {/if}

  <div class="grid">
    {#each roster as w, i}
      <div class="card wc">
        <div class="wc-top">
          <span class="rank mono">#{i + 1}</span>
          <a class="addr mono" href={tv(w.addr)} target="_blank" rel="noopener" title={w.addr}>{w.name || short(w.addr)}</a>
          <span class="n" title="в скольких отслеживаемых токенах — топ-холдер">{w.n}×</span>
        </div>
        <div class="chips">
          {#each w.toks as t}<span class="chip" class:new={w.new?.includes(t)}>{t}</span>{/each}
        </div>
      </div>
    {/each}
  </div>
  <p class="muted small foot">Метрика: breadth = число отслеживаемых токенов, где кошелёк входит в топ-{25} холдеров (CEX/DEX/пулы/скам отфильтрованы). Сам по себе breadth — это «whale-конвикшн по экосистеме»; настоящий copy-сигнал — раздел «новые входы», он наполняется со второго дня (нужен предыдущий снапшот для диффа).</p>
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
  .chips{display:flex;flex-wrap:wrap;gap:4px}
  .chip{font-size:11px;padding:2px 7px;border-radius:6px;background:rgba(255,255,255,.05);color:var(--muted)}
  .chip.new{background:rgba(34,167,255,.18);color:var(--accent)}
  .mono{font-family:ui-monospace,Menlo,Consolas,monospace}
  .foot{margin-top:16px;max-width:680px;line-height:1.5}
</style>
