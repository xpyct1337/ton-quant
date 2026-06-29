<script>
  import { onMount } from 'svelte';
  import { loadDeskStatus, loadDeskCalibration, loadDeskFactors, loadDeskCopytrade } from '$lib/data.js';

  let status = $state(undefined); // undefined=loading, null=not run yet, obj=ran
  let calib = $state(undefined);
  let factors = $state(undefined);
  let copytrade = $state(undefined);
  const copy = (t) => navigator.clipboard?.writeText(t);
  const pct = (x) => (x == null ? '—' : (x * 100 >= 0 ? '+' : '') + (x * 100).toFixed(1) + '%');

  let wallets = $derived(status?.wallets || []);
  let risk = $derived.by(() => {
    const r = { low: 0, med: 0, high: 0 };
    for (const w of wallets) if (w.manip_risk in r) r[w.manip_risk]++;
    return r;
  });
  let copyOk = $derived(wallets.filter((w) => w.copy_ok).length);

  // calibration: +7d avg excess return by risk bucket (high should be most negative)
  let h7 = $derived(calib?.feature_backtest?.['+7d']);
  // researcher: active learned factors + attempt counts from the history log
  let active = $derived(factors?.active || []);
  let fcount = $derived.by(() => {
    const c = { proposed: 0, promoted: 0, rejected: 0, demoted: 0 };
    for (const e of factors?.history || []) if (e.action in c) c[e.action]++;
    return c;
  });

  // conytail: best small models for 8GB M1 Air (research 27.06.2026) — 4B is the
  // sweet spot (7B swaps on 8GB; 2026 4B reasons better than 2025 7B).
  const models = [
    { name: 'Qwen3 4B', pull: 'ollama pull qwen3:4b', ram: '~4.5 ГБ', note: 'основная — сильное рассуждение + надёжный JSON', best: true },
    { name: 'Gemma 3 4B', pull: 'ollama pull gemma3:4b', ram: '~4.2 ГБ', note: '100% JSON-parse, но добавляет болтовню вокруг (стрипать); самая экономная' },
    { name: 'Phi-4-mini 3.8B', pull: 'ollama pull phi4-mini', ram: '~3.5 ГБ', note: 'быстрая (15–20 t/s), если 4B тяжелит' },
    { name: 'Llama 3.2 3B', pull: '—', ram: '~2.5 ГБ', note: 'не брать для деска — JSON-parse ~50%', avoid: true }
  ];

  const setup = [
    { t: 'Ollama + модель', cmds: ['brew install ollama', 'ollama serve', 'ollama pull qwen3:4b'] },
    { t: 'Оптимизация под 8 ГБ (в ~/.zshrc)', cmds: ['export OLLAMA_FLASH_ATTENTION=1', 'export OLLAMA_KV_CACHE_TYPE=q8_0'] },
    { t: 'Репозиторий (с git-кредами для push)', cmds: ['git clone git@github.com:xpyct1337/ton-quant.git', 'cd ton-quant'] },
    { t: 'Python-зависимость', cmds: ['pip3 install requests'] },
    { t: 'Прогон деска (скрипт придёт с MVP)', cmds: ['python3 scripts/desk.py'] }
  ];

  onMount(async () => {
    status = await loadDeskStatus();
    calib = await loadDeskCalibration();
    factors = await loadDeskFactors();
    copytrade = await loadDeskCopytrade();
  });
</script>

<svelte:head><title>TON Quant — AI Desk</title></svelte:head>

{#snippet cmd(text)}
  <div class="cmd"><code>{text}</code><button class="cp" onclick={() => copy(text)} aria-label="копировать"><i class="ti ti-copy"></i></button></div>
{/snippet}

<header class="hd">
  <h1>AI Smart-Money Desk</h1>
  <span class="muted">пульт деска на MacBook (M1) — локальный LLM вётит smart-money и режет манипуляцию. Сетап, выбор модели и статус ночных прогонов.</span>
</header>

<section class="card">
  <div class="ttl"><i class="ti ti-activity"></i> Статус деска</div>
  {#if status === undefined}
    <div class="muted pad">Загружаю…</div>
  {:else if status === null}
    <div class="muted">Деск ещё не запускался. После первого ночного прогона на Mac (пишет <code>data/desk/verdicts.json</code>) здесь появятся: дата, модель, сколько кошельков провёчено и разбивка по риску.</div>
  {:else}
    <div class="kpis">
      <div class="kpi"><span class="kl">последний прогон</span><span class="kv">{status.date}</span></div>
      <div class="kpi"><span class="kl">модель</span><span class="kv mono">{status.model}</span></div>
      <div class="kpi"><span class="kl">кошельков</span><span class="kv">{wallets.length}</span></div>
      <div class="kpi"><span class="kl">copy_ok</span><span class="kv up">{copyOk}</span></div>
      <div class="kpi"><span class="kl">риск L/M/H</span><span class="kv"><span class="up">{risk.low}</span>/<span class="amber">{risk.med}</span>/<span class="down">{risk.high}</span></span></div>
    </div>
  {/if}
</section>

<section class="card">
  <div class="ttl"><i class="ti ti-target-arrow"></i> Само-калибровка сигнала</div>
  {#if calib === undefined}
    <div class="muted pad">Загружаю…</div>
  {:else if !calib || !h7}
    <div class="muted">Калибровка ещё не посчитана (появится после прогона воркера). Проверяет: предсказывает ли <code>manip_risk</code> будущую просадку — сверяет вердикты с реальной forward-доходностью.</div>
  {:else}
    <div class="muted small">forward excess-доходность токенов через +7д по бакету риска. Гипотеза: <b>high &lt; med &lt; low</b> (рисковые проседают).</div>
    <div class="kpis">
      <div class="kpi"><span class="kl">снапшотов</span><span class="kv">{calib.snapshots}</span></div>
      <div class="kpi"><span class="kl">low +7д</span><span class="kv up">{pct(h7.low?.avg)}</span></div>
      <div class="kpi"><span class="kl">med +7д</span><span class="kv amber">{pct(h7.med?.avg)}</span></div>
      <div class="kpi"><span class="kl">high +7д</span><span class="kv down">{pct(h7.high?.avg)}</span></div>
      <div class="kpi"><span class="kl">сигнал разделяет</span><span class="kv" class:up={calib.signal_separates_at_7d} class:down={!calib.signal_separates_at_7d}>{calib.signal_separates_at_7d ? 'да' : 'нет'}</span></div>
    </div>
  {/if}
</section>

<section class="card">
  <div class="ttl"><i class="ti ti-flask"></i> Агент-ресёрчер (факторы)</div>
  {#if factors === undefined}
    <div class="muted pad">Загружаю…</div>
  {:else}
    <div class="muted small">LLM 24/7 предлагает факторы → walk-forward OOS-гейт (анти-оверфит) → выжившие авто-вливаются в риск. Floors остаются жёсткими.</div>
    <div class="kpis">
      <div class="kpi"><span class="kl">активных</span><span class="kv up">{active.length}/8</span></div>
      <div class="kpi"><span class="kl">попыток</span><span class="kv">{fcount.proposed}</span></div>
      <div class="kpi"><span class="kl">промоут</span><span class="kv up">{fcount.promoted}</span></div>
      <div class="kpi"><span class="kl">реджект</span><span class="kv muted">{fcount.rejected}</span></div>
    </div>
    {#if active.length}
      <div class="models">
        {#each active as f}
          <div class="mrow"><span class="mname mono">{f.id}</span><span class="mram muted small">{f.direction}</span><span class="mnote muted small">oos_lo {f.metrics?.oos?.wilson_lo ?? '—'}</span></div>
        {/each}
      </div>
    {:else}
      <div class="muted small">Пока ни один фактор не прошёл гейт — это правильно: на малой истории строгий OOS-порог почти ничего не пропускает (анти-оверфит). Реальные факторы появятся по мере накопления снапшотов.</div>
    {/if}
  {/if}
</section>

<section class="card">
  <div class="ttl"><i class="ti ti-arrows-split"></i> Copy-trading: вётчено vs всё</div>
  {#if copytrade === undefined}
    <div class="muted pad">Загружаю…</div>
  {:else if !copytrade}
    <div class="muted">Ещё не посчитано (появится после прогона воркера). Сравнивает копирование всех roster-кошельков против только <code>copy_ok</code>-вётченных.</div>
  {:else}
    <div class="muted small">forward excess на +{copytrade.horizon}д. Сигнал = первый вход кошелька в токен. Вётчено кошельков: {copytrade.copyok_wallets}.</div>
    <div class="kpis">
      <div class="kpi"><span class="kl">copy-all n / avg</span><span class="kv">{copytrade.copy_all.n} / <span class={copytrade.copy_all.avg < 0 ? 'down' : 'up'}>{(copytrade.copy_all.avg * 100).toFixed(1)}%</span></span></div>
      <div class="kpi"><span class="kl">copy-desk n / avg</span><span class="kv">{copytrade.copy_desk.n} / <span class={copytrade.copy_desk.avg < 0 ? 'down' : 'up'}>{(copytrade.copy_desk.avg * 100).toFixed(1)}%</span></span></div>
      <div class="kpi"><span class="kl">edge (desk−all)</span><span class="kv" class:up={copytrade.edge >= 0} class:down={copytrade.edge < 0}>{(copytrade.edge * 100).toFixed(1)}%</span></div>
    </div>
    {#if copytrade.note}<div class="muted small">{copytrade.note}</div>{/if}
  {/if}
</section>

<section class="card">
  <div class="ttl"><i class="ti ti-cpu"></i> Модель LLM (для 8 ГБ M1 Air)</div>
  <div class="muted small">актуально на 27.06.2026. На 8 ГБ MLX-бэкенд недоступен (нужно 32 ГБ) — остаёмся на Metal.</div>
  <div class="models">
    {#each models as m}
      <div class="mrow" class:best={m.best} class:avoid={m.avoid}>
        <span class="mname">{m.name}{#if m.best}<span class="tag">рек.</span>{/if}</span>
        <span class="mram mono">{m.ram}</span>
        <span class="mnote muted small">{m.note}</span>
        {#if !m.avoid}{@render cmd(m.pull)}{/if}
      </div>
    {/each}
  </div>
</section>

<section class="card">
  <div class="ttl"><i class="ti ti-terminal-2"></i> Установка на Mac</div>
  {#each setup as s, i}
    <div class="step">
      <div class="step-h"><span class="num">{i + 1}</span>{s.t}</div>
      {#each s.cmds as c}{@render cmd(c)}{/each}
    </div>
  {/each}
  <div class="step">
    <div class="step-h"><span class="num">6</span>launchd — ночной прогон (plist придёт с оркестрацией E2)</div>
    <div class="muted small">после установки деск будет сам стартовать ночью и при включении Mac (RunAtLoad catch-up).</div>
  </div>
</section>

<section class="card note">
  <div class="ttl"><i class="ti ti-info-circle"></i> Про управление с этой страницы</div>
  <p class="muted small">Сайт — статика (GitHub Pages), он <b>не может слать команды на Mac</b> напрямую — для этого нужен бэкенд или токен. Честный путь без бэкенда: деск читает <code>data/desk/config.json</code> из репо (модель / вкл-выкл / лимит ростера), а мы правим этот файл. Кнопки управления добавлю, когда появится способ писать конфиг (Action с workflow_dispatch или мелкий бэкенд). <span class="mono">conytail: фейковые кнопки-«пуск» не рисую — пульт только читает, пока нет реального канала записи.</span></p>
</section>

<style>
  .hd{margin-bottom:16px;display:flex;flex-direction:column;gap:6px}
  h1{font-family:var(--head);font-size:22px;margin:0}
  .small{font-size:12px}
  .pad{padding:14px 0}
  .card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:13px 15px;margin-bottom:14px}
  .ttl{font-family:var(--head);font-size:14px;display:flex;align-items:center;gap:7px;margin-bottom:8px}
  .note{border-color:rgba(34,167,255,.3);background:rgba(34,167,255,.05)}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px}
  .kpi{display:flex;flex-direction:column;gap:3px}
  .kl{font-size:11px;color:var(--muted)}
  .kv{font-family:var(--head);font-size:18px;font-weight:600}
  .up{color:#41d68a}.down{color:#ff6b6b}.amber{color:#ffae57}
  .mono{font-family:ui-monospace,Menlo,Consolas,monospace}
  .models{display:flex;flex-direction:column;gap:7px;margin-top:8px}
  .mrow{display:grid;grid-template-columns:130px 70px 1fr auto;gap:10px;align-items:center;padding:6px 0;border-bottom:1px solid var(--border)}
  .mrow:last-child{border-bottom:none}
  .mrow.best{background:rgba(65,214,138,.05)}
  .mrow.avoid{opacity:.6}
  .mname{font-size:13px;font-weight:600;display:flex;align-items:center;gap:6px}
  .tag{font-size:10px;background:rgba(65,214,138,.16);color:#41d68a;border-radius:5px;padding:1px 5px}
  @media(max-width:620px){.mrow{grid-template-columns:1fr auto;row-gap:4px}.mnote{grid-column:1/-1}}
  .step{padding:8px 0;border-bottom:1px solid var(--border)}
  .step:last-child{border-bottom:none}
  .step-h{font-size:13px;display:flex;align-items:center;gap:8px;margin-bottom:6px}
  .num{width:20px;height:20px;flex:none;border-radius:6px;background:rgba(255,255,255,.07);display:flex;align-items:center;justify-content:center;font-size:11px;color:var(--muted)}
  .cmd{display:flex;align-items:center;gap:8px;background:#0a0e16;border:1px solid var(--border);border-radius:7px;padding:5px 8px;margin:3px 0}
  .cmd code{flex:1;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;color:var(--text);overflow-x:auto;white-space:nowrap}
  .cp{flex:none;background:none;border:none;color:var(--muted);cursor:pointer;padding:2px;font-size:15px}
  .cp:hover{color:var(--accent)}
  p{line-height:1.55;margin:4px 0 0}
</style>
