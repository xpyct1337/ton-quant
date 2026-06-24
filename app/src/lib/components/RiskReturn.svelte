<script>
  import { lrets, dstats, corrColor } from '$lib/metrics.js';
  let { rows = [] } = $props();

  const AX = '#2a3344', MUT = '#7c8497', LBL = '#c9d2e0';

  let model = $derived.by(() => {
    const out = rows.filter((r) => r.core && r.hist)
      .map((r) => {
        const spark = r.hist.map((h) => h?.price).filter((p) => p > 0);
        if (spark.length < 12) return null;
        const s = dstats(lrets(spark)); if (!s) return null;
        return { sym: r.sym, ann: s.mean * 365 * 100, vol: s.std * Math.sqrt(365) * 100, sh: s.std > 0 ? s.mean / s.std * Math.sqrt(365) : 0, mc: Math.max(r.mcap || 1, 1) };
      }).filter(Boolean);
    if (out.length < 3) return null;

    const W = 640, H = 360, pl = 52, pr = 14, pt = 14, pb = 42, iw = W - pl - pr, ih = H - pt - pb;
    const rMin = 4, rMax = 20, sMin = Math.sqrt(Math.min(...out.map((r) => r.mc))), sMax = Math.sqrt(Math.max(...out.map((r) => r.mc)));
    const rad = (mc) => (sMax > sMin ? rMin + (rMax - rMin) * (Math.sqrt(mc) - sMin) / (sMax - sMin) : rMin + 2);
    const vmax = Math.max(...out.map((r) => r.vol)) * 1.08 || 1;
    let amin = Math.min(0, ...out.map((r) => r.ann)), amax = Math.max(0, ...out.map((r) => r.ann));
    const padv = (amax - amin) * 0.08 || 1; amin -= padv; amax += padv;
    const X = (v) => pl + (v / vmax) * iw, Y = (a) => pt + ih - ((a - amin) / (amax - amin)) * ih;
    const cc = (v) => corrColor(Math.max(-1, Math.min(1, v)));
    const bubbles = out.slice().sort((a, b) => b.mc - a.mc).map((r) => ({ ...r, x: X(r.vol), y: Y(r.ann), rr: rad(r.mc) }));
    const yTicks = [0, 1, 2, 3, 4].map((k) => { const a = amin + (amax - amin) * k / 4; return { a, y: Y(a) }; });
    const xTicks = [0, 1, 2, 3, 4].map((k) => { const v = vmax * k / 4; return { v, x: X(v) }; });
    const rk = out.slice().sort((a, b) => b.sh - a.sh);
    return { W, H, pl, pr, pt, ih, iw, amin, amax, Y, bubbles, yTicks, xTicks, cc, rk, zeroY: amin < 0 && amax > 0 ? Y(0) : null, n: out.length };
  });
</script>

{#if !model}
  <div class="empty">Накапливаю историю — нужно ≥12 дней снапшотов на токен.</div>
{:else}
  <svg viewBox="0 0 {model.W} {model.H}" class="rr">
    {#if model.zeroY != null}<line x1={model.pl} y1={model.zeroY} x2={model.W - model.pr} y2={model.zeroY} stroke={AX} stroke-dasharray="4 3" />{/if}
    <line x1={model.pl} y1={model.pt} x2={model.pl} y2={model.pt + model.ih} stroke={AX} />
    <line x1={model.pl} y1={model.pt + model.ih} x2={model.W - model.pr} y2={model.pt + model.ih} stroke={AX} />
    {#each model.yTicks as t}<text x={model.pl - 6} y={t.y + 3} text-anchor="end" font-size="9" fill={MUT}>{t.a >= 0 ? '+' : ''}{t.a.toFixed(0)}%</text>{/each}
    {#each model.xTicks as t}<text x={t.x} y={model.pt + model.ih + 14} text-anchor="middle" font-size="9" fill={MUT}>{t.v.toFixed(0)}%</text>{/each}
    <text x={model.pl + model.iw / 2} y={model.H - 4} text-anchor="middle" font-size="10" fill={MUT}>annualized volatility</text>
    <text x="13" y={model.pt + model.ih / 2} text-anchor="middle" font-size="10" fill={MUT} transform="rotate(-90 13 {model.pt + model.ih / 2})">annualized return</text>
    {#each model.bubbles as b}
      <circle cx={b.x.toFixed(1)} cy={b.y.toFixed(1)} r={b.rr.toFixed(1)} fill={model.cc(b.sh)} fill-opacity="0.82" stroke="#5a6472" stroke-width="0.6">
        <title>{b.sym} — return {b.ann.toFixed(0)}% / vol {b.vol.toFixed(0)}% / Sharpe {b.sh.toFixed(2)}</title>
      </circle>
      <text x={(b.x + b.rr + 3).toFixed(1)} y={(b.y + 3).toFixed(1)} font-size="9" fill={LBL}>{b.sym}</text>
    {/each}
    <text x={model.W - model.pr} y={model.pt + 8} text-anchor="end" font-size="9" fill={MUT}>размер = mcap</text>
  </svg>
  <div class="wrap">
    <table class="rt">
      <thead><tr><th></th><th class="r">ann. return</th><th class="r">ann. vol</th><th class="r">Sharpe</th></tr></thead>
      <tbody>
        {#each model.rk.slice(0, 8) as r}
          <tr>
            <th class="rh">{r.sym}</th>
            <td class="r cell" style="background:{model.cc(r.ann > 0 ? 0.5 : -0.5)}">{r.ann >= 0 ? '+' : ''}{r.ann.toFixed(0)}%</td>
            <td class="r m">{r.vol.toFixed(0)}%</td>
            <td class="r cell" style="background:{model.cc(r.sh)}">{r.sh.toFixed(2)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <div class="note">Лучший risk-adjusted: <strong>{model.rk[0].sym}</strong> (Sharpe {model.rk[0].sh.toFixed(2)}). Худший: <strong>{model.rk[model.rk.length - 1].sym}</strong> (Sharpe {model.rk[model.rk.length - 1].sh.toFixed(2)}). {model.n} токенов, ~40 дневных закрытий, rf=0. Площадь пузыря ∝ mcap.</div>
{/if}

<style>
  .rr{width:100%;max-width:640px;height:auto;display:block;font-family:inherit}
  .wrap{overflow-x:auto;margin-top:8px}
  .rt{width:100%;border-collapse:collapse;font-size:12px}
  .rt th{color:var(--dim);font-weight:400;padding:4px 8px;font-size:11px;text-align:left}
  .rt .r{text-align:right;font-family:var(--mono)}
  .rt td{padding:5px 8px;border-top:1px solid var(--border)}
  .rt .rh{text-align:left;color:var(--text);font-weight:500}
  .rt .m{color:var(--muted)}
  .note{font-size:12px;color:var(--muted);margin-top:10px;line-height:1.5}
  .note strong{color:var(--text)}
  .empty{color:var(--muted);font-size:13px;padding:24px 4px}
</style>
