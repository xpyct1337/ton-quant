<script>
  import { onMount } from 'svelte';
  import { loadAll, liveRates } from '$lib/data.js';
  import { WIDGETS, GROUPS, PRESETS } from '$lib/widgets.js';
  import { prefs, toggle, showAll, hideAll, applyPreset } from '$lib/dashboardPrefs.svelte.js';

  let state = $state('loading');
  let rows = $state([]);
  let meta = $state({});

  onMount(async () => {
    try {
      const d = await loadAll(40); // full snapshot history → longer sparks for analytics
      const live = await liveRates(d.rows.map((r) => r.addr));
      for (const r of d.rows) { const p = live[r.addr]; if (p && r.price > 0) { r.mcap *= p / r.price; r.price = p; } }
      rows = d.rows;
      meta = { updated: d.updated, snaps: d.snapCount };
      state = 'ready';
    } catch (e) {
      state = 'error';
      meta = { err: String(e.message || e) };
    }
  });

  let visible = $derived(WIDGETS.filter((w) => w.ready && prefs.visible.has(w.id)));
  const presetNames = Object.keys(PRESETS);
  // widgets grouped for the toggle palette
  const byGroup = GROUPS.map((g) => ({ g, items: WIDGETS.filter((w) => w.group === g) })).filter((x) => x.items.length);
</script>

<svelte:head><title>TON Quant — Analytics</title></svelte:head>

<header class="hd">
  <div class="hd-top">
    <h1>Analytics</h1>
    {#if meta.updated}<span class="muted upd">snapshot {meta.updated} · {meta.snaps} дней</span>{/if}
  </div>
</header>

{#if state === 'loading'}
  <div class="muted pad">Загружаю onchain-данные…</div>
{:else if state === 'error'}
  <div class="card bad">Не удалось загрузить данные: {meta.err}</div>
{:else}
  <!-- Control bar: presets + show/hide all -->
  <section class="ctl card">
    <div class="ctl-row">
      <span class="ctl-lbl">Профиль</span>
      {#each presetNames as p}
        <button class="chip" class:on={prefs.preset === p} onclick={() => applyPreset(p)}>{p}</button>
      {/each}
      <span class="spacer"></span>
      <button class="chip ghost" onclick={showAll}>Включить всё</button>
      <button class="chip ghost" onclick={hideAll}>Свернуть всё</button>
    </div>
    <div class="ctl-groups">
      {#each byGroup as grp}
        <div class="grp">
          <span class="grp-lbl">{grp.g}</span>
          {#each grp.items as w}
            <button class="chip sm" class:on={prefs.visible.has(w.id)} class:soon={!w.ready}
              disabled={!w.ready} title={w.ready ? w.desc : w.desc + ' · скоро'}
              onclick={() => toggle(w.id)}>{w.title}{!w.ready ? ' ·скоро' : ''}</button>
          {/each}
        </div>
      {/each}
    </div>
  </section>

  <!-- Widget grid: only visible widgets mount/compute -->
  {#if visible.length}
    <section class="grid">
      {#each visible as w (w.id)}
        <div class="wcard card" style="grid-column:span {Math.min(w.span, 2)}">
          <div class="whead">
            <div><div class="wt">{w.title}</div><div class="wd muted">{w.desc}</div></div>
            <button class="x" title="Скрыть" onclick={() => toggle(w.id)}>×</button>
          </div>
          <w.component {rows} />
        </div>
      {/each}
    </section>
  {:else}
    <div class="muted pad">Все дашборды свёрнуты — выбери профиль или включи виджеты выше.</div>
  {/if}
{/if}

<style>
  .hd{margin-bottom:16px}
  .hd-top{display:flex;align-items:baseline;gap:12px}
  h1{font-size:24px}
  .upd{font-size:12px}
  .pad{padding:30px 0}
  section{margin-bottom:18px}
  .ctl{padding:14px 16px}
  .ctl-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .ctl-lbl{color:var(--muted);font-size:12px;margin-right:2px}
  .spacer{flex:1}
  .ctl-groups{display:flex;flex-wrap:wrap;gap:14px;margin-top:12px;padding-top:12px;border-top:1px solid var(--border)}
  .grp{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
  .grp-lbl{color:var(--dim);font-size:11px;margin-right:2px}
  .chip{background:var(--card2);border:1px solid var(--border);color:var(--muted);
    padding:5px 11px;border-radius:8px;font-size:13px;cursor:pointer}
  .chip:hover{color:var(--text)}
  .chip.on{background:rgba(34,167,255,.14);border-color:var(--accent);color:var(--accent)}
  .chip.ghost{background:transparent}
  .chip.sm{font-size:12px;padding:4px 9px}
  .chip.soon{opacity:.45;cursor:not-allowed}
  .grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
  .wcard{padding:16px 18px;min-width:0}
  .whead{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:12px}
  .wt{font-family:var(--head);font-weight:600;font-size:15px}
  .wd{font-size:12px;margin-top:2px}
  .x{background:transparent;border:none;color:var(--dim);font-size:20px;line-height:1;cursor:pointer;padding:0 4px}
  .x:hover{color:var(--text)}
  @media(max-width:860px){.grid{grid-template-columns:1fr}.wcard{grid-column:span 1 !important}}
</style>
