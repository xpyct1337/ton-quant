<script>
  import { onMount } from 'svelte';
  import { normalizeMindmapNode } from '$lib/mindmap.js';
  const nodes = [
    ['sources', 'Источники идей'],
    ['hypothesis', 'Гипотеза'],
    ['experiment', 'Минимальный эксперимент'],
    ['validation', 'Forward / paper-test']
  ];
  const branches = [
    ['desk', 'AI Smart-Money Desk'],
    ['showcase', 'Витрина'],
    ['log', 'Журнал решений'],
    ['data', 'GitHub Actions → data/*.json'],
    ['ledger', 'Source ledger'],
    ['history', 'Point-in-time universe history']
  ];
  const details = {
    sources: ['Источники идей', 'Научные статьи и первичные данные дают основание; свежие AI-работы и Reddit дают кандидатов на проверку.'],
    hypothesis: ['Гипотеза', 'Формулируем измеримый эффект, baseline, ожидаемый механизм и условие отказа до написания кода.'],
    experiment: ['Минимальный эксперимент', 'Используем уже собранные данные и самый короткий тест, способный опровергнуть идею.'],
    validation: ['Forward / paper-test', 'Проверяем вне обучающей выборки, учитываем комиссии, leakage, множественные проверки и стабильность во времени.'],
    desk: ['AI Smart-Money Desk', 'Детерминированные фичи задают безопасный floor, LLM синтезирует оценку, а калибровка проверяет её на будущих данных.'],
    showcase: ['Витрина', 'Brief, analytics, wallets и desk показывают проверенные результаты и возвращают наблюдения в новый цикл гипотез.'],
    log: ['Журнал решений', 'ROADMAP-v3.md хранит результат, причины принятия или отказа и следующий проверяемый вопрос.'],
    data: ['Поток данных', 'GitHub Actions собирает снимки в data/*.json; Desk и статическая витрина общаются только через файлы в Git.'],
    ledger: ['Source ledger', 'Одна замороженная гипотеза на запуск, детерминированный OOS-gate и никакого автоматического промоута факторов.'],
    history: ['Point-in-time universe history', 'Hourly append-only OKX snapshots. Статус остаётся collecting, пока истории недостаточно для survivorship-aware исследования.']
  };

  let selected = $state('sources');
  let submitState = $state('');
  let selectedDetail = $derived(details[selected]);

  function select(id) {
    selected = normalizeMindmapNode(id);
    submitState = '';
    if (typeof window !== 'undefined') {
      localStorage.setItem('tq_mindmap_selected', selected);
      const url = new URL(window.location.href);
      url.searchParams.set('node', selected);
      window.history.replaceState(null, '', url);
    }
  }

  onMount(() => {
    const urlNode = new URL(window.location.href).searchParams.get('node');
    const savedNode = localStorage.getItem('tq_mindmap_selected');
    select(normalizeMindmapNode(urlNode || savedNode));
  });

  async function submit() {
    const [title, description] = selectedDetail;
    const prompt = `Продолжить TON Quant по ветке «${title}». ${description}\n\nВыбери следующий фальсифицируемый минимальный шаг по Ponytail, реализуй и проверь его. Обновляй docs/PROJECT-MAP.md и ROADMAP-v3.md только если меняется решение.`;
    if (window.openai?.sendFollowUpMessage) {
      await window.openai.sendFollowUpMessage({ title: `Развить ветку «${title}»`, prompt });
      submitState = 'sent';
      return;
    }
    await navigator.clipboard?.writeText(prompt).catch(() => {});
    const issue = `https://github.com/xpyct1337/ton-quant/issues/new?title=${encodeURIComponent('TON Quant: ' + title)}&body=${encodeURIComponent(prompt)}`;
    window.open(issue, '_blank', 'noopener');
    submitState = 'opened';
  }
</script>

<svelte:head><title>Mindmap — TON Quant</title></svelte:head>

<header class="hd">
  <div class="hd-top"><h1>Mindmap</h1><span class="muted">выбери следующую ветку разработки</span></div>
</header>

<section class="map" aria-label="Основной исследовательский цикл TON Quant">
  <div class="flow">
    {#each nodes as node, i}
      <button type="button" class="node" class:selected={selected === node[0]} aria-pressed={selected === node[0]} onclick={() => select(node[0])}>{node[1]}</button>
      {#if i < nodes.length - 1}<span class="arrow" aria-hidden="true">→</span>{/if}
    {/each}
  </div>

  <div class="branches" aria-label="Ветви результата и инфраструктуры">
    <div class="branch-label muted">Если эффект подтверждён</div>
    <div class="flow">
      {#each branches.slice(0, 2) as branch}
        <button type="button" class="node" class:selected={selected === branch[0]} aria-pressed={selected === branch[0]} onclick={() => select(branch[0])}>{branch[1]}</button>
      {/each}
    </div>
    <div class="branch-label muted">Если эффекта нет или мало данных</div>
    <div class="flow">
      {#each branches.slice(2, 3) as branch}
        <button type="button" class="node" class:selected={selected === branch[0]} aria-pressed={selected === branch[0]} onclick={() => select(branch[0])}>{branch[1]}</button>
      {/each}
    </div>
    <div class="flow infra">
      {#each branches.slice(3) as branch}
        <button type="button" class="node" class:selected={selected === branch[0]} aria-pressed={selected === branch[0]} onclick={() => select(branch[0])}>{branch[1]}</button>
      {/each}
    </div>
  </div>
</section>

<section class="card detail" aria-live="polite">
  <div><strong>{selectedDetail[0]}</strong><p class="muted">{selectedDetail[1]}</p></div>
  <button type="button" class="submit" onclick={submit}>Submit → разработка</button>
  {#if submitState === 'sent'}<span class="status good">Отправлено в текущий Codex task.</span>{/if}
  {#if submitState === 'opened'}<span class="status good">GitHub issue подготовлен; текст также скопирован.</span>{/if}
</section>

<style>
  .hd{margin-bottom:16px}.hd-top{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}h1{font-size:24px}.map{display:grid;gap:16px}.flow{display:flex;justify-content:center;align-items:center;gap:8px;flex-wrap:wrap}.node{font:inherit;color:var(--text);background:var(--card2);border:1px solid var(--border);border-radius:9px;padding:8px 11px;cursor:pointer}.node:hover,.node.selected{color:var(--accent);border-color:rgba(34,167,255,.55);background:rgba(34,167,255,.1)}.arrow{color:var(--muted)}.branches{display:grid;gap:9px;padding:12px 0;border-block:1px solid var(--border)}.branch-label{text-align:center;font-size:12px}.infra{padding-top:8px}.detail{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}.detail p{margin:5px 0 0;max-width:720px;line-height:1.5}.submit{background:var(--accent);color:#04223b;border:0;border-radius:9px;padding:9px 13px;font-weight:500;cursor:pointer}.status{font-size:12px}.good{color:var(--good)}
  @media(max-width:520px){.detail{align-items:stretch;flex-direction:column}.submit{width:100%}}
</style>
