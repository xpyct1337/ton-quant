<script>
  import { washVerdict } from '$lib/metrics.js';
  import { fmtUsd } from '$lib/format.js';
  let { rows = [] } = $props();

  let model = $derived.by(() => {
    const out = rows.filter((r) => r.core && r.tvl > 0 && r.vol24 >= 0)
      .map((r) => {
        const turnover = r.vol24 / r.tvl;
        const txns = (r.buys || 0) + (r.sells || 0);
        return { sym: r.sym, turnover, txns, avgTrade: txns > 0 ? r.vol24 / txns : 0, verdict: washVerdict(turnover) };
      })
      .sort((a, b) => b.turnover - a.turnover);
    return out.length >= 3 ? out : null;
  });
  const lbl = { wash: '🚿 likely wash', elevated: '⚠ elevated', ok: 'ok' };
</script>

{#if !model}
  <div class="empty">Недостаточно токенов с ликвидностью.</div>
{:else}
  <div class="wrap">
    <table class="w">
      <thead><tr><th></th><th class="r">vol/TVL (turnover)</th><th class="r">24h сделок</th><th class="r">средний $/сделка</th><th>вердикт</th></tr></thead>
      <tbody>
        {#each model as r}
          <tr>
            <th class="rh">{r.sym}</th>
            <td class="r cell" class:hi={r.turnover >= 5} class:mid={r.turnover >= 3 && r.turnover < 5}>{r.turnover.toFixed(1)}x</td>
            <td class="r m">{r.txns}</td>
            <td class="r m">{fmtUsd(r.avgTrade)}</td>
            <td class="v" class:wash={r.verdict === 'wash'} class:el={r.verdict === 'elevated'}>{lbl[r.verdict]}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <div class="note">Турновер = дневной объём / ликвидность пула. Реальный DEX-объём редко держит &gt;3–5x/день без накрутки. Эвристика, не доказательство: высокий turnover при крошечном числе сделок = объём крутят между своими.</div>
{/if}

<style>
  .wrap{overflow-x:auto}
  .w{width:100%;border-collapse:collapse;font-size:12px}
  .w th{color:var(--dim);font-weight:400;padding:4px 8px;font-size:11px;text-align:left}
  .w .r{text-align:right;font-family:var(--mono)}
  .w td{padding:6px 8px;border-top:1px solid var(--border)}
  .w .rh{text-align:left;color:var(--text);font-weight:500}
  .w .m{color:var(--muted)}
  .cell.mid{background:rgba(214,158,46,.16);color:#e0a93a}
  .cell.hi{background:rgba(207,79,95,.2);color:#e06a78}
  .v{color:var(--muted)} .v.el{color:#e0a93a} .v.wash{color:#e06a78;font-weight:600}
  .note{font-size:12px;color:var(--muted);margin-top:10px;line-height:1.5}
  .empty{color:var(--muted);font-size:13px;padding:24px 4px}
</style>
