<script>
  import { base } from '$app/paths';
  let { card } = $props();
</script>

<a class="ac" href="{base}/token?a={card.addr}">
  <div class="ac-top">
    <i class="ti {card.icon} tone-{card.tone}"></i>
    <span class="ac-agent">{card.agent}</span>
    {#if card.when}<span class="ac-when muted">{card.when}</span>{/if}
  </div>
  <div class="ac-text">{card.text}</div>
</a>

<style>
  .ac{display:block;border:1px solid var(--border);border-radius:12px;padding:12px 14px;background:var(--card)}
  .ac:hover{border-color:rgba(255,255,255,.18)}
  .ac-top{display:flex;align-items:center;gap:8px;margin-bottom:6px}
  .ac-top i{font-size:16px}
  .ac-agent{font-size:13px;font-weight:500}
  .ac-when{margin-left:auto;font-size:11px}
  .ac-text{font-size:13px;color:#cdd4df;line-height:1.55}
  .tone-good{color:var(--good)} .tone-bad{color:var(--bad)} .tone-warn{color:var(--warn)} .tone-info{color:var(--accent)}
</style>
