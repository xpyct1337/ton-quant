<script>
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { base } from '$app/paths';
  import { loadWallet } from '$lib/data.js';
  import { featuredWallets, walletAddress } from '$lib/wallets.js';
  import { fmtUsd, fmtNum, shortAddr } from '$lib/format.js';

  let st = $state('loading');
  let wallet = $state(null);
  let err = $state('');
  let updated = $state(null);
  let address = $state('');

  const meta = $derived(featuredWallets.find((item) => item.address === address));

  async function refresh() {
    try {
      wallet = await loadWallet(address);
      updated = new Date();
      st = 'ready';
    } catch (e) {
      err = e.message || String(e);
      st = 'error';
    }
  }

  onMount(() => {
    address = walletAddress($page.params.address || '');
    if (!address) { st = 'error'; err = 'Адрес кошелька не указан'; return; }
    refresh();
    const iv = setInterval(() => { if (!document.hidden) refresh(); }, 60000);
    const onVis = () => { if (!document.hidden) refresh(); };
    document.addEventListener('visibilitychange', onVis);
    return () => { clearInterval(iv); document.removeEventListener('visibilitychange', onVis); };
  });
</script>

<svelte:head><title>{meta?.label || 'Кошелёк'} — TON Quant</title></svelte:head>

{#if st === 'loading'}
  <div class="muted pad">Загружаю данные кошелька…</div>
{:else if st === 'error'}
  <div class="card bad">Не удалось загрузить кошелёк: {err}</div>
{:else}
  <header class="hero">
    <div>
      <div class="eyebrow">SMART MONEY · LIVE</div>
      <h1>{meta?.label || wallet.name || 'TON wallet'}</h1>
      <div class="addr mono">{address}</div>
      <div class="actions">
        <a class="btn" href={'https://tonviewer.com/' + address} target="_blank" rel="noopener">Открыть в Tonviewer ↗</a>
        <span class="muted sm">обновлено {updated?.toLocaleTimeString() || '—'}</span>
      </div>
    </div>
  </header>

  <section class="kpis">
    <div class="kc"><div class="kl">Общая стоимость</div><div class="kv mono">{fmtUsd(wallet.total)}</div></div>
    <div class="kc"><div class="kl">TON</div><div class="kv mono">{wallet.ton.toFixed(2)}</div><div class="muted sm">{fmtUsd(wallet.tonValue)}</div></div>
    <div class="kc"><div class="kl">Жетоны с ценой</div><div class="kv mono">{wallet.holdings.length}</div></div>
  </section>

  <section class="card">
    <div class="sec-title">Портфель <span class="muted">· live TONAPI · обновление 60s</span></div>
    {#if wallet.holdings.length}
      <div class="tw"><table>
        <thead><tr><th>Монета</th><th class="r">Количество</th><th class="r">Цена</th><th class="r">Стоимость</th><th class="r">Доля</th></tr></thead>
        <tbody>
          {#each wallet.holdings as holding}
            <tr>
              <td><a class="sym" href={`${base}/token?a=${holding.addr}`}>{holding.sym}</a></td>
              <td class="r mono">{fmtNum(holding.amount)}</td>
              <td class="r mono">{fmtUsd(holding.price)}</td>
              <td class="r mono">{fmtUsd(holding.usd)}</td>
              <td class="r mono">{wallet.total ? (holding.usd / wallet.total * 100).toFixed(1) + '%' : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table></div>
    {:else}
      <p class="muted sm">TONAPI не вернул жетоны с ненулевой оценкой.</p>
    {/if}
  </section>

  <section class="card note">
    <div class="sec-title">Как читать страницу</div>
    <p class="muted sm">Это обновляемый on-chain snapshot: баланс и оценки приходят напрямую из TONAPI, а ссылки на жетоны ведут на их страницы TON Quant. Историческая доходность и намерения владельца здесь не выводятся без подтверждённой истории транзакций.</p>
  </section>
{/if}

<style>
  .pad{padding:30px 0}.hero{margin-bottom:16px}.eyebrow{color:var(--accent);font-size:11px;letter-spacing:.1em;margin-bottom:8px}.addr{color:var(--muted);font-size:12px;overflow-wrap:anywhere;margin-top:6px}h1{font-size:25px;margin:0}.actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:12px}.btn{color:var(--accent);font-size:12px;border:1px solid var(--border);border-radius:8px;padding:6px 10px}.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}.kc{background:var(--card2);border-radius:12px;padding:13px 15px}.kl{color:var(--muted);font-size:12px;margin-bottom:6px}.kv{font-size:20px}.sm{font-size:12px}.tw{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:13px}th{color:var(--dim);font-weight:400;text-align:left;padding:7px 10px;font-size:11px;white-space:nowrap}td{padding:9px 10px;border-top:1px solid var(--border);white-space:nowrap}.r{text-align:right}.sym{font-weight:500}.note{margin-top:16px;line-height:1.5}.bad{color:var(--bad)}
  @media(max-width:600px){.kpis{grid-template-columns:1fr}.addr{font-size:11px}}
</style>
