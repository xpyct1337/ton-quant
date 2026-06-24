<script>
  import { winRet, rsComposite, corrColor } from '$lib/metrics.js';
  let { rows = [] } = $props();
  const wins = [7, 14, 30];

  let model = $derived.by(() => {
    let rs = rows
      .filter((r) => r.core && r.hist)
      .map((r) => ({ sym: r.sym, addr: r.addr, spark: r.hist.map((h) => h?.price).filter((p) => p > 0) }))
      .filter((x) => x.spark.length >= 5)
      .map((x) => ({ ...x, ret: wins.map((n) => winRet(x.spark, n)) }))
      .filter((x) => x.ret.some((v) => v != null));
    if (rs.length < 3) return null;

    const rsNow = rsComposite(rs.map((x) => x.ret));
    const rsPrev = rsComposite(rs.map((x) => wins.map((n) => winRet(x.spark.slice(0, x.spark.length - 7), n))));
    rs.forEach((x, i) => { x.rs = rsNow[i] ?? 0; x.dRs = rsNow[i] != null && rsPrev[i] != null ? rsNow[i] - rsPrev[i] : null; });
    rs.sort((a, b) => b.rs - a.rs);
    return rs;
  });

  const cbg = (v) => (v == null ? 'transparent' : corrColor(Math.max(-1, Math.min(1, v / 30))));
</script>

{#if !model}
  <div class="empty">Накапливаю историю — нужно ≥5 дней снапшотов.</div>
{:else}
  <div class="wrap">
    <table class="mom">
      <thead><tr><th></th><th>7d</th><th>14d</th><th>30d</th><th class="rs">RS</th><th>тренд</th></tr></thead>
      <tbody>
        {#each model as x, i}
          <tr>
            <th class="rh">{i + 1}. {x.sym}</th>
            {#each x.ret as v}
              <td style="background:{cbg(v)}">{v == null ? '—' : (v >= 0 ? '+' : '') + v.toFixed(0) + '%'}</td>
            {/each}
            <td class="rs">{x.rs.toFixed(0)}</td>
            <td class="tr" class:up={x.dRs > 3} class:dn={x.dRs < -3}>
              {x.dRs == null ? '—' : (x.dRs > 3 ? '▲' : x.dRs < -3 ? '▼' : '→') + ' ' + (x.dRs >= 0 ? '+' : '') + x.dRs.toFixed(0)}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <div class="note">RS = средний перцентиль по 7/14/30d. Тренд = изменение RS против недели назад. {model.length} токенов.</div>
{/if}

<style>
  .wrap{overflow-x:auto}
  .mom{width:100%;border-collapse:collapse;font-size:12px;font-family:var(--mono)}
  .mom th{color:var(--dim);font-weight:400;padding:4px 7px;font-size:11px;text-align:right}
  .mom thead th:first-child{text-align:left}
  .mom td{padding:5px 7px;text-align:right;border-top:1px solid var(--border)}
  .mom .rh{text-align:left;color:var(--text);white-space:nowrap;font-weight:500}
  .mom .rs{font-weight:600;color:var(--text)}
  .mom .tr{color:var(--muted)} .mom .tr.up{color:#2e9e5b} .mom .tr.dn{color:#cf4f5f}
  .note{font-size:12px;color:var(--muted);margin-top:10px;line-height:1.5}
  .empty{color:var(--muted);font-size:13px;padding:24px 4px}
</style>
