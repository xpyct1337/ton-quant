<script>
  import { onMount } from 'svelte';
  import { fmtPct } from '$lib/format.js';
  import { loadSignals } from '$lib/data.js';

  const RAW = 'https://raw.githubusercontent.com/xpyct1337/ton-quant/main/data';
  const PERP_URL = RAW + '/perp_signals.json';
  const DEX_URL  = RAW + '/dex_signals.json';

  let st    = $state('loading');
  let bot   = $state(null);
  let dex   = $state(null);
  let chain = $state(null);
  let date  = $state('');

  onMount(async () => {
    const [botR, dexR, sigR] = await Promise.allSettled([
      fetch(PERP_URL).then((r) => (r.ok ? r.json() : null)),
      fetch(DEX_URL).then((r)  => (r.ok ? r.json() : null)),
      loadSignals()
    ]);
    if (botR.status === 'fulfilled' && botR.value?.signals?.length) bot = botR.value;
    if (dexR.status === 'fulfilled' && dexR.value?.signals?.length) dex = dexR.value;
    if (sigR.status === 'fulfilled') {
      const s = sigR.value;
      if (s.today?.signals?.length) { chain = s; date = s.date || ''; }
    }
    st = 'ready';
  });

  const sideCls  = (side) => (side === 'long' || side === 'buy' ? 'good' : side === 'short' || side === 'sell' ? 'bad' : '');
  const sideTxt  = (side) => side?.toUpperCase() ?? '—';
  const fmtTime  = (ts) => new Date(typeof ts === 'number' ? ts * 1000 : ts).toLocaleString();
  const verdCls  = (v) => (v === 'edge' ? 'good' : v === 'noise' ? 'bad' : 'muted');
  const sigScore = (sig, scores) => scores?.by_signal?.[sig];
</script>

<svelte:head><title>TG Signals — TON Quant</title></svelte:head>

<header class="hd">
  <h1><i class="ti ti-brand-telegram"></i> TG Signals</h1>
  <span class="muted">сигналы из Telegram-каналов + on-chain события отслеживаемых жетонов</span>
</header>

{#if st === 'loading'}
  <div class="muted pad">Загружаю сигналы…</div>
{:else}

  <!-- @perptools_ai_bot -->
  <section class="card tw">
    <div class="sec-title">
      <i class="ti ti-robot"></i> @perptools_ai_bot
      {#if bot}<span class="muted">· обновлено {fmtTime(bot.updated)}</span>{/if}
    </div>
    {#if !bot}
      <p class="muted sm">Нет данных — сигналы появятся после настройки секрета <code>TG_SESSION</code> в GitHub Actions.</p>
    {:else}
      <table>
        <thead><tr>
          <th>Время</th><th>Coin</th><th>Side</th>
          <th class="r">Entry</th><th class="r">Targets</th><th class="r">Stop</th><th class="r">Lev</th>
        </tr></thead>
        <tbody>
          {#each bot.signals.slice(0, 50) as s}
            <tr>
              <td class="muted">{fmtTime(s.ts)}</td>
              <td><span class="sym">{s.coin}</span></td>
              <td class={sideCls(s.side)}>{sideTxt(s.side)}</td>
              <td class="r mono">{s.entry ?? '—'}</td>
              <td class="r mono">{s.tps?.join(' / ') ?? '—'}</td>
              <td class="r mono">{s.sl ?? '—'}</td>
              <td class="r mono">{s.lev ? s.lev + 'x' : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>

  <!-- @dexnewtoken -->
  <section class="card tw">
    <div class="sec-title">
      <i class="ti ti-currency-dollar"></i> @dexnewtoken
      {#if dex}<span class="muted">· обновлено {fmtTime(dex.updated)}</span>{/if}
    </div>
    {#if !dex}
      <p class="muted sm">Нет данных — канал публичный, проверь <code>scripts/dex_signals.py</code>.</p>
    {:else}
      <table>
        <thead><tr>
          <th>Дата</th><th>Symbol</th><th>Side</th>
          <th class="r">Price</th><th class="r">Target</th><th>Адрес</th>
        </tr></thead>
        <tbody>
          {#each dex.signals.slice(0, 50) as s}
            <tr>
              <td class="muted">{fmtTime(s.dt)}</td>
              <td><span class="sym">{s.sym ?? '—'}</span></td>
              <td class={sideCls(s.side)}>{sideTxt(s.side)}</td>
              <td class="r mono">{s.price ?? '—'}</td>
              <td class="r mono">{s.target ?? '—'}</td>
              <td class="mono muted">{s.addr ? s.addr.slice(0, 8) + '…' + s.addr.slice(-6) : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>

  <!-- On-chain signal events (daily tracked set) -->
  <section class="card tw">
    <div class="sec-title">
      <i class="ti ti-circuit-diode"></i> On-chain события
      {#if date}<span class="muted">· {date}</span>{/if}
    </div>
    {#if !chain}
      <p class="muted sm">Нет данных за сегодня — снапшот появится после 03:10 UTC.</p>
    {:else}
      <table>
        <thead><tr>
          <th>Жетон</th><th>Сигнал</th><th class="r">Цена</th>
          <th class="r">TVL</th><th class="r">Vol 24h</th>
          <th class="r">Вес</th><th>Вердикт</th>
        </tr></thead>
        <tbody>
          {#each chain.today.signals as s}
            {@const sc = sigScore(s.sig, chain.scores)}
            <tr>
              <td><span class="sym">{s.sym ?? s.addr?.slice(0, 6)}</span></td>
              <td class="sig-name">{s.sig.replace(/_/g, ' ')}</td>
              <td class="r mono">{s.price != null ? '$' + s.price.toPrecision(4) : '—'}</td>
              <td class="r mono">{s.tvl != null ? '$' + Math.round(s.tvl / 1000) + 'K' : '—'}</td>
              <td class="r mono">{s.vol24 != null ? '$' + Math.round(s.vol24 / 1000) + 'K' : '—'}</td>
              <td class="r mono">{s.w ?? '—'}</td>
              <td>
                {#if sc}
                  <span class="pill {verdCls(sc.verdict)}">{sc.verdict}</span>
                  {#if sc.d1_mean != null}<span class="mono muted">{fmtPct(sc.d1_mean)}</span>{/if}
                {:else}
                  <span class="muted sm">collecting</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>

  <p class="foot muted">
    @perptools_ai_bot: сигналы из личного чата с ботом через Telethon (scripts/perp_signals.py, воркфлоу каждые 4ч).
    @dexnewtoken: публичный канал, парсинг t.me/s (scripts/dex_signals.py).
    On-chain события: паттерны momentum, liq_inflow, breakout и др. на отслеживаемых 24 жетонах; вердикт (edge/noise/collecting) по реализованным форвард-доходностям.
    Не финансовый совет.
  </p>
{/if}

<style>
  .hd{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:18px}
  .hd i{color:var(--accent);font-size:22px}
  h1{font-size:24px;display:flex;align-items:center;gap:8px}
  .pad{padding:30px 0}
  section{margin-bottom:16px}
  .sm{font-size:13px;line-height:1.5}
  .sec-title{display:flex;align-items:center;gap:8px;margin-bottom:10px;font-weight:500}
  .sec-title i{font-size:16px;color:var(--accent)}
  table{width:100%;border-collapse:collapse;font-size:13px}.tw{overflow-x:auto}
  th{color:var(--dim);font-weight:400;text-align:left;padding:6px 9px;font-size:11px;white-space:nowrap}
  td{padding:8px 9px;border-top:1px solid var(--border);white-space:nowrap}
  .r{text-align:right}
  .sym{font-weight:500}
  .sig-name{text-transform:lowercase;color:var(--muted)}
  .pill{font-size:11px;padding:2px 8px;border-radius:6px;background:var(--card2)}
  .pill.good{color:var(--good)}.pill.bad{color:var(--bad)}.pill.muted{color:var(--muted)}
  .good{color:var(--good)}.bad{color:var(--bad)}
  code{background:var(--card2);padding:1px 6px;border-radius:5px;font-family:var(--mono)}
  .foot{font-size:11px;margin-top:14px;line-height:1.6;max-width:740px}
</style>
