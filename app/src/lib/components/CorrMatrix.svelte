<script>
  import { lrets, pcorr, betaVs, corrColor } from '$lib/metrics.js';
  let { rows = [] } = $props();

  let model = $derived.by(() => {
    const sel = rows
      .filter((r) => r.core && r.hist)
      .map((r) => ({ sym: r.sym, addr: r.addr, mcap: r.mcap || 0, spark: r.hist.map((h) => h?.price).filter((p) => p > 0) }))
      .filter((r) => r.spark.length >= 6)
      .sort((a, b) => b.mcap - a.mcap)
      .slice(0, 12);
    if (sel.length < 3) return null;

    const L = Math.min(...sel.map((t) => t.spark.length));
    const series = sel.map((t) => lrets(t.spark.slice(-L)));
    const steps = L - 1;
    const market = [];
    for (let i = 0; i < steps; i++) { let s = 0; for (const r of series) s += r[i]; market.push(s / series.length); }
    const C = series.map((a) => series.map((b) => pcorr(a, b)));
    const betas = series.map((a) => betaVs(a, market));

    let pa = -1, pb = -1, pv = -2;
    for (let i = 0; i < C.length; i++) for (let j = i + 1; j < C.length; j++) { const v = C[i][j]; if (v != null && v > pv) { pv = v; pa = i; pb = j; } }
    const avg = C.map((row, i) => { let s = 0, c = 0; row.forEach((v, j) => { if (i !== j && v != null) { s += v; c++; } }); return c ? s / c : null; });
    let mi = -1, mv = 2; avg.forEach((v, i) => { if (v != null && v < mv) { mv = v; mi = i; } });

    return { sel, C, betas, steps, note: pa >= 0 && mi >= 0 ? { pair: [sel[pa].sym, sel[pb].sym], pv, div: sel[mi].sym, mv } : null };
  });

  const bbg = (b) => (b == null ? 'transparent' : corrColor(b >= 1 ? 0.7 : b < 0 ? -0.7 : 0));
</script>

{#if !model}
  <div class="empty">Накапливаю историю — нужно ≥6 дней снапшотов на токен.</div>
{:else}
  <div class="wrap">
    <table class="corr">
      <thead>
        <tr><th></th>{#each model.sel as t}<th>{t.sym}</th>{/each}<th class="b">β</th></tr>
      </thead>
      <tbody>
        {#each model.sel as t, i}
          <tr>
            <th class="rh">{t.sym}</th>
            {#each model.C[i] as v, j}
              <td style="background:{corrColor(v)}" title="{t.sym} vs {model.sel[j].sym}">{v == null ? '—' : i === j ? '1.00' : v.toFixed(2)}</td>
            {/each}
            <td class="b" style="background:{bbg(model.betas[i])}">{model.betas[i] == null ? '—' : model.betas[i].toFixed(2)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  {#if model.note}
    <div class="note">Связаны сильнее всех: <strong>{model.note.pair[0]}–{model.note.pair[1]}</strong> (r {model.note.pv.toFixed(2)}). Лучший диверсификатор: <strong>{model.note.div}</strong> (avg r {model.note.mv.toFixed(2)}). {model.steps + 1} дней.</div>
  {/if}
{/if}

<style>
  .wrap{overflow-x:auto}
  .corr{border-collapse:collapse;font-size:11px;font-family:var(--mono)}
  .corr th{color:var(--dim);font-weight:400;padding:3px 5px;font-size:10px}
  .corr .rh{text-align:right;color:var(--text);white-space:nowrap}
  .corr td{padding:4px 6px;text-align:center;border-radius:3px;color:var(--text);min-width:34px}
  .corr .b{font-weight:600}
  .note{font-size:12px;color:var(--muted);margin-top:10px;line-height:1.5}
  .note strong{color:var(--text)}
  .empty{color:var(--muted);font-size:13px;padding:24px 4px}
</style>
