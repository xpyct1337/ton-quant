<script>
  // Warns when the data pipeline went quiet. `when` = ISO date of the last daily
  // run or a unix ts (seconds); silent while fresher than `maxHours`.
  import { staleHours } from '$lib/metrics.js';
  let { when, maxHours = 30, what = 'снапшот' } = $props();
  let h = $derived(staleHours(when));
</script>

{#if h != null && h > maxHours}
  <div class="stale">
    <i class="ti ti-alert-triangle"></i>
    Данные устарели: последний {what} — {Math.round(h)}ч назад. Пайплайн сбора молчит.
  </div>
{/if}

<style>
  .stale{display:flex;align-items:center;gap:8px;background:rgba(240,153,58,.1);
    border:1px solid rgba(240,153,58,.35);color:#f0b35c;border-radius:10px;
    padding:9px 13px;font-size:13px;margin-bottom:14px}
  .stale i{font-size:16px;flex:none}
</style>
