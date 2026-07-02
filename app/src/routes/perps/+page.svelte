<script>
  import { onMount } from 'svelte';
  import { loadPerpSignals } from '$lib/data.js';
  import StaleBanner from '$lib/components/StaleBanner.svelte';

  let st = $state('loading');
  let raw = $state(null);

  let filter = $state('all'); // 'all' | 'long' | 'short'
  let showRaw = $state({});

  const ago = (ts) => {
    const d = Math.floor((Date.now() / 1000 - ts) / 60);
    if (d < 60) return d + 'м';
    if (d < 1440) return Math.floor(d / 60) + 'ч';
    return Math.floor(d / 1440) + 'д';
  };
  const fmtPrice = (p) => p == null ? null : p >= 1000 ? p.toFixed(0) : p >= 1 ? p.toFixed(3) : p.toFixed(6);
  const fmtTs = (ts) => new Date(ts * 1000).toLocaleString('ru', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

  let signals = $derived(raw?.signals || []);
  let filtered = $derived(filter === 'all' ? signals : signals.filter((s) => s.side === filter));
  let longs = $derived(signals.filter((s) => s.side === 'long').length);
  let shorts = $derived(signals.filter((s) => s.side === 'short').length);

  onMount(async () => {
    try {
      raw = await loadPerpSignals();
      st = raw ? 'ready' : 'empty';
    } catch {
      st = 'error';
    }
  });
</script>

<svelte:head><title>TON Quant — Perp Signals</title></svelte:head>

<header class="hd">
  <div class="hd-top">
    <h1>Perp signals</h1>
    <span class="muted small">сигналы от <span class="mono">@perptools_ai_bot</span> · парсинг через Telegram MTProto · каждые 4 часа</span>
  </div>
</header>

{#if st === 'loading'}
  <div class="muted pad">Загружаю сигналы…</div>
{:else if st === 'error'}
  <div class="card bad">Не удалось загрузить сигналы.</div>
{:else if st === 'empty'}
  <div class="card note">
    <b>Данных пока нет.</b> Воркфлоу <span class="mono">perp-signals.yml</span> собирает сигналы каждые 4 часа — нужно настроить секреты <span class="mono">TG_API_ID</span>, <span class="mono">TG_API_HASH</span>, <span class="mono">TG_SESSION</span> и запустить вручную через Actions.
  </div>
{:else}
  <StaleBanner when={raw.updated} maxHours={10} what="обновление сигналов" />

  <section class="kpis">
    <div class="kpi"><span class="kl">всего сигналов</span><span class="kv">{signals.length}</span></div>
    <div class="kpi"><span class="kl">лонги</span><span class="kv up">{longs}</span></div>
    <div class="kpi"><span class="kl">шорты</span><span class="kv dn">{shorts}</span></div>
    <div class="kpi"><span class="kl">обновлено</span><span class="kv small mono">{raw.updated?.slice(0, 16).replace('T', ' ')}</span></div>
  </section>

  <div class="filters">
    <button class="fb" class:act={filter === 'all'} onclick={() => filter = 'all'}>Все {signals.length}</button>
    <button class="fb up" class:act={filter === 'long'} onclick={() => filter = 'long'}>▲ Long {longs}</button>
    <button class="fb dn" class:act={filter === 'short'} onclick={() => filter = 'short'}>▼ Short {shorts}</button>
  </div>

  {#if filtered.length === 0}
    <div class="muted pad">Нет сигналов по фильтру.</div>
  {:else}
    <div class="grid">
      {#each filtered as s (s.id)}
        <div class="sig" class:long={s.side === 'long'} class:short={s.side === 'short'}>
          <div class="sig-top">
            <span class="coin">{s.coin}</span>
            <span class="side" class:up={s.side === 'long'} class:dn={s.side === 'short'}>
              {s.side === 'long' ? '▲ LONG' : '▼ SHORT'}
            </span>
            {#if s.lev}<span class="lev">{s.lev}×</span>{/if}
            <span class="ts muted small mono">{ago(s.ts)}</span>
          </div>

          <div class="levels">
            {#if s.entry != null}
              <div class="lrow"><span class="ll muted">вход</span><span class="lv mono">{fmtPrice(s.entry)}</span></div>
            {/if}
            {#if s.tps?.length}
              {#each s.tps as tp, i}
                <div class="lrow tp"><span class="ll muted">TP{s.tps.length > 1 ? i + 1 : ''}</span><span class="lv mono up">{fmtPrice(tp)}</span></div>
              {/each}
            {/if}
            {#if s.sl != null}
              <div class="lrow sl"><span class="ll muted">SL</span><span class="lv mono dn">{fmtPrice(s.sl)}</span></div>
            {/if}
          </div>

          {#if s.entry && s.sl}
            {@const rr = s.side === 'long'
              ? ((s.tps?.[0] ?? s.entry) - s.entry) / (s.entry - s.sl)
              : (s.entry - (s.tps?.[0] ?? s.entry)) / (s.sl - s.entry)}
            {#if isFinite(rr) && rr > 0}
              <div class="rr muted small">R:R <span class:up={rr >= 2} class:warn={rr > 0 && rr < 2}>{rr.toFixed(1)}</span></div>
            {/if}
          {/if}

          <div class="sig-foot">
            <span class="ts-full muted small">{fmtTs(s.ts)}</span>
            <button class="raw-btn muted small" onclick={() => showRaw[s.id] = !showRaw[s.id]}>
              {showRaw[s.id] ? 'скрыть' : 'raw'}
            </button>
          </div>

          {#if showRaw[s.id]}
            <pre class="raw">{s.raw}</pre>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
{/if}

<style>
  .hd{margin-bottom:16px}
  .hd-top{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
  h1{font-family:var(--head);font-size:22px;margin:0}
  .small{font-size:12px}
  .pad{padding:20px 0}
  .bad{color:#ff6b6b}
  .card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 14px;margin-bottom:14px}
  .note{border-color:rgba(34,167,255,.35);background:rgba(34,167,255,.05)}

  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-bottom:14px}
  .kpi{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:11px 13px;display:flex;flex-direction:column;gap:3px}
  .kl{font-size:11px;color:var(--muted)}
  .kv{font-family:var(--head);font-size:20px;font-weight:600}
  .kv.small{font-size:13px}
  .up{color:#41d68a}
  .dn{color:#ff6b6b}
  .warn{color:#f0997b}
  .kv.up{color:#41d68a}
  .kv.dn{color:#ff6b6b}
  .mono{font-family:ui-monospace,Menlo,Consolas,monospace}

  .filters{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
  .fb{background:var(--card);border:1px solid var(--border);color:var(--muted);border-radius:8px;
    padding:6px 14px;cursor:pointer;font-size:13px;transition:all .15s}
  .fb:hover{color:var(--text);border-color:rgba(255,255,255,.2)}
  .fb.act{background:rgba(255,255,255,.08);color:var(--text);border-color:rgba(255,255,255,.2)}
  .fb.up.act{background:rgba(65,214,138,.12);color:#41d68a;border-color:rgba(65,214,138,.3)}
  .fb.dn.act{background:rgba(255,107,107,.12);color:#ff6b6b;border-color:rgba(255,107,107,.3)}

  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}

  .sig{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 14px;
    display:flex;flex-direction:column;gap:8px}
  .sig.long{border-left:3px solid rgba(65,214,138,.5)}
  .sig.short{border-left:3px solid rgba(255,107,107,.5)}

  .sig-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .coin{font-family:var(--head);font-size:17px;font-weight:600}
  .side{font-size:11px;font-weight:700;padding:2px 7px;border-radius:5px}
  .side.up{background:rgba(65,214,138,.15);color:#41d68a}
  .side.dn{background:rgba(255,107,107,.14);color:#ff6b6b}
  .lev{font-size:11px;background:rgba(255,255,255,.07);border-radius:5px;padding:2px 6px;color:var(--muted)}
  .ts{margin-left:auto;font-size:11px}

  .levels{display:flex;flex-direction:column;gap:3px}
  .lrow{display:flex;justify-content:space-between;align-items:center;font-size:12px}
  .lrow.tp .lv{color:#41d68a}
  .lrow.sl .lv{color:#ff6b6b}
  .ll{min-width:36px}
  .lv{font-size:13px;font-weight:500}

  .rr{font-size:11px}
  .rr span{font-weight:600}

  .sig-foot{display:flex;justify-content:space-between;align-items:center;margin-top:2px}
  .ts-full{font-size:11px}
  .raw-btn{background:none;border:none;cursor:pointer;padding:0;font-family:inherit;font-size:11px}
  .raw-btn:hover{color:var(--text)}
  pre.raw{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px;color:var(--muted);
    white-space:pre-wrap;word-break:break-word;background:rgba(255,255,255,.03);
    border-radius:6px;padding:8px;margin:0;line-height:1.5}
</style>
