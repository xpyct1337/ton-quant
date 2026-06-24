<script>
  import { absorptionSignal } from '$lib/metrics.js';
  let { rows = [] } = $props();

  let model = $derived.by(() => {
    const out = rows.filter((r) => r.core)
      .map((r) => {
        const txns = (r.buys || 0) + (r.sells || 0);
        return { sym: r.sym, br: txns > 0 ? r.buys / txns * 100 : null, txns, d1: r.d1, sig: absorptionSignal(r.buys, r.sells, r.d1) };
      })
      .filter((x) => x.br != null && x.txns >= 20);
    if (out.length < 3) return null;
    out.sort((a, b) => (b.sig ? 1 : 0) - (a.sig ? 1 : 0) || b.txns - a.txns);
    return out;
  });
  const lbl = { sell_wall: 'стена продавца', accumulation: 'тихий выкуп' };
</script>

{#if !model}
  <div class="empty">Недостаточно сделок для чтения потока (нужно ≥20 за 24ч).</div>
{:else}
  <div class="wrap">
    <table class="ab">
      <thead><tr><th></th><th>buy / sell поток</th><th class="r">buy %</th><th class="r">24h сделок</th><th class="r">1d %</th><th>сигнал</th></tr></thead>
      <tbody>
        {#each model as r}
          <tr>
            <th class="rh">{r.sym}</th>
            <td><div class="bar"><div class="fill" style="width:{r.br.toFixed(0)}%"></div></div></td>
            <td class="r m">{r.br.toFixed(0)}%</td>
            <td class="r m">{r.txns}</td>
            <td class="r mono" class:up={r.d1 > 0} class:dn={r.d1 < 0}>{r.d1 == null ? '—' : (r.d1 >= 0 ? '+' : '') + r.d1.toFixed(1) + '%'}</td>
            <td class="sig" class:wall={r.sig === 'sell_wall'} class:acc={r.sig === 'accumulation'}>{r.sig ? lbl[r.sig] : '—'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <div class="note">Поток покупок против цены. Много покупок при флэте/падении = <strong>стена продавца</strong> поглощает спрос. Много продаж при флэте/росте = кто-то <strong>тихо выкупает</strong>. Расхождение потока и цены = чья-то крупная позиция.</div>
{/if}

<style>
  .wrap{overflow-x:auto}
  .ab{width:100%;border-collapse:collapse;font-size:12px}
  .ab th{color:var(--dim);font-weight:400;padding:4px 8px;font-size:11px;text-align:left}
  .ab .r{text-align:right;font-family:var(--mono)} .ab .mono{font-family:var(--mono)}
  .ab td{padding:6px 8px;border-top:1px solid var(--border)}
  .ab .rh{text-align:left;color:var(--text);font-weight:500}
  .ab .m{color:var(--muted)}
  .bar{position:relative;height:8px;border-radius:4px;min-width:120px;background:rgba(207,79,95,.35);overflow:hidden}
  .fill{position:absolute;left:0;top:0;height:100%;background:rgba(46,158,91,.6)}
  .up{color:#2e9e5b} .dn{color:#cf4f5f}
  .sig{color:var(--muted)} .sig.wall{color:#e06a78;font-weight:600} .sig.acc{color:#2e9e5b;font-weight:600}
  .note{font-size:12px;color:var(--muted);margin-top:10px;line-height:1.5}
  .note strong{color:var(--text)}
  .empty{color:var(--muted);font-size:13px;padding:24px 4px}
</style>
