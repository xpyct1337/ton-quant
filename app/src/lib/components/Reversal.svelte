<script>
  import { rsiDiv, macdDiv } from '$lib/metrics.js';
  let { rows = [] } = $props();

  let model = $derived.by(() => {
    const out = rows.filter((r) => r.core && r.hist)
      .map((r) => {
        const spark = r.hist.map((h) => h?.price).filter((p) => p > 0);
        const rd = rsiDiv(spark), md = macdDiv(spark);
        const rt = (rd && rd.type) || null, mt = (md && md.type) || null;
        if (!rt && !mt) return null;
        if (rt && mt && rt !== mt) return null; // conflict → not actionable
        if (rt && mt) return { sym: r.sym, type: rt, conf: 'both' };
        return { sym: r.sym, type: rt || mt, conf: rt ? 'rsi' : 'macd' };
      }).filter(Boolean);
    if (!out.length) return null;
    const rk = { both: 0, rsi: 1, macd: 1 };
    out.sort((a, b) => rk[a.conf] - rk[b.conf] || (a.type < b.type ? -1 : 1));
    return out;
  });
</script>

{#if !model}
  <div class="empty">Нет дивергенций на радаре — либо рынок спокоен, либо мало истории (нужно ≥35 дней для MACD).</div>
{:else}
  <div class="wrap">
    <table class="rev">
      <thead><tr><th></th><th>сигнал</th><th>подтверждён</th><th>сила</th></tr></thead>
      <tbody>
        {#each model as r}
          <tr>
            <th class="rh">{r.sym}</th>
            <td class="sig" class:bull={r.type === 'bull'} class:bear={r.type === 'bear'}>{r.type === 'bull' ? '▲ bullish' : '▼ bearish'}</td>
            <td>
              <span class="chip" class:on={r.conf !== 'macd'}>RSI</span>
              <span class="chip" class:on={r.conf !== 'rsi'}>MACD</span>
            </td>
            <td class="str" class:cfm={r.conf === 'both'}>{r.conf === 'both' ? 'confirmed' : 'single'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <div class="note">Двойное подтверждение (RSI + MACD расходятся с ценой одинаково) — сигнал разворота сильнее любого одиночного; single-строки — раннее предупреждение в ожидании второго. Снимок, не прогноз. {model.length} {model.length === 1 ? 'токен' : 'токенов'} на радаре.</div>
{/if}

<style>
  .wrap{overflow-x:auto}
  .rev{width:100%;border-collapse:collapse;font-size:12px}
  .rev th{color:var(--dim);font-weight:400;padding:4px 8px;font-size:11px;text-align:left}
  .rev td{padding:6px 8px;border-top:1px solid var(--border)}
  .rev .rh{text-align:left;color:var(--text);font-weight:500}
  .sig{font-weight:600;color:var(--muted)} .sig.bull{color:#2e9e5b} .sig.bear{color:#cf4f5f}
  .chip{display:inline-block;padding:1px 7px;border-radius:4px;font-size:11px;margin-right:4px;background:rgba(255,255,255,.07);color:var(--dim)}
  .chip.on{background:var(--accent);color:#04223b;font-weight:600}
  .str{color:var(--muted)} .str.cfm{color:var(--text);font-weight:600}
  .note{font-size:12px;color:var(--muted);margin-top:10px;line-height:1.5}
  .note strong{color:var(--text)}
  .empty{color:var(--muted);font-size:13px;padding:24px 4px}
</style>
