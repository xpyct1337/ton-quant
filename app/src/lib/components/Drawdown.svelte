<script>
  import { corrColor } from '$lib/metrics.js';
  let { rows = [] } = $props();

  let model = $derived.by(() => {
    const out = rows.filter((r) => r.core && r.hist)
      .map((r) => {
        const a = r.hist.map((h) => h?.price).filter((p) => p > 0);
        if (a.length < 5) return null;
        const last = a[a.length - 1], hi = Math.max(...a), lo = Math.min(...a);
        return { sym: r.sym, dd: (last - hi) / hi * 100, pos: hi > lo ? (last - lo) / (hi - lo) * 100 : 50 };
      }).filter(Boolean);
    if (out.length < 3) return null;
    out.sort((x, y) => x.dd - y.dd);
    return out;
  });
  const clamp = (p) => Math.max(0, Math.min(100, p));
</script>

{#if !model}
  <div class="empty">Накапливаю историю — нужно ≥5 дней снапшотов.</div>
{:else}
  <div class="wrap">
    <table class="dd">
      <thead><tr><th></th><th class="r">просадка</th><th>диапазон (low→high)</th><th class="r">поз</th></tr></thead>
      <tbody>
        {#each model as r}
          <tr>
            <th class="rh">{r.sym}</th>
            <td class="r cell" style="background:{corrColor(Math.max(-1, r.dd / 40))}">{r.dd >= -0.05 ? '0%' : r.dd.toFixed(0) + '%'}</td>
            <td>
              <div class="track"><div class="mk" style="left:calc({clamp(r.pos).toFixed(0)}% - 4px);background:{corrColor(clamp(r.pos) / 50 - 1)}"></div></div>
            </td>
            <td class="r m">{r.pos.toFixed(0)}%</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <div class="note">Глубже всех просадка: <strong>{model[0].sym}</strong> ({model[0].dd.toFixed(0)}% от 40д-хая). Ближе всех к хаю: <strong>{model[model.length - 1].sym}</strong> ({model[model.length - 1].dd >= -0.05 ? 'на новом хае' : model[model.length - 1].dd.toFixed(0) + '% от хая'}, поз {model[model.length - 1].pos.toFixed(0)}%). {model.length} токенов.</div>
{/if}

<style>
  .wrap{overflow-x:auto}
  .dd{width:100%;border-collapse:collapse;font-size:12px}
  .dd th{color:var(--dim);font-weight:400;padding:4px 8px;font-size:11px;text-align:left}
  .dd .r{text-align:right;font-family:var(--mono)}
  .dd td{padding:6px 8px;border-top:1px solid var(--border)}
  .dd .rh{text-align:left;color:var(--text);font-weight:500}
  .dd .m{color:var(--muted)}
  .track{position:relative;height:10px;background:rgba(255,255,255,.07);border-radius:5px;min-width:130px}
  .mk{position:absolute;top:-1px;width:8px;height:12px;border-radius:2px;border:1px solid #5a6472}
  .note{font-size:12px;color:var(--muted);margin-top:10px;line-height:1.5}
  .note strong{color:var(--text)}
  .empty{color:var(--muted);font-size:13px;padding:24px 4px}
</style>
