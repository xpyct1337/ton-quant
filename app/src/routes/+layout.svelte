<script>
  import '$lib/style.css';
  import { base } from '$app/paths';
  let { children } = $props();
  const nav = [
    { href: base + '/', label: 'Markets', icon: 'ti-home', active: true },
    { href: base + '/analytics', label: 'Analytics', icon: 'ti-chart-dots' },
    { href: base + '/screener', label: 'Screener', icon: 'ti-list-search' },
    { href: base + '/compare', label: 'Compare', icon: 'ti-arrows-diff' },
    { href: base + '/portfolio', label: 'Portfolio', icon: 'ti-wallet' },
    { href: base + '/paper', label: 'Paper bot', icon: 'ti-robot' }
  ];
</script>

<svelte:head>
  <title>TON Quant — Markets</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.19.0/dist/tabler-icons.min.css" />
</svelte:head>

<div class="shell">
  <aside class="side">
    <div class="logo"><span class="mark">Q</span><span class="name">TON Quant</span></div>
    <nav>
      {#each nav as n}
        <a class="navlink" class:active={n.active} href={n.href}><i class="ti {n.icon}"></i><span>{n.label}</span></a>
      {/each}
    </nav>
    <div class="side-foot muted">v2 · live onchain</div>
  </aside>
  <main>{@render children()}</main>
</div>

<style>
  .shell{display:flex;min-height:100vh}
  .side{width:var(--nav);flex:none;background:#0a0e16;border-right:1px solid var(--border);
    padding:18px 12px;display:flex;flex-direction:column;gap:6px;position:sticky;top:0;height:100vh}
  .logo{display:flex;align-items:center;gap:9px;padding:4px 8px 16px}
  .mark{width:26px;height:26px;border-radius:7px;background:var(--accent);color:#04223b;
    display:flex;align-items:center;justify-content:center;font-family:var(--head);font-weight:600}
  .name{font-family:var(--head);font-weight:600;font-size:15px}
  .navlink{display:flex;align-items:center;gap:10px;padding:9px 11px;border-radius:9px;color:var(--muted);font-size:14px}
  .navlink:hover{background:var(--card);color:var(--text)}
  .navlink.active{background:rgba(34,167,255,.13);color:var(--accent)}
  .navlink i{font-size:18px}
  .side-foot{margin-top:auto;padding:8px;font-size:11px}
  main{flex:1;min-width:0;padding:22px 26px;max-width:1180px}
  @media(max-width:640px){
    .shell{display:block}
    .side{position:fixed;inset:auto 0 0 0;width:auto;height:auto;flex-direction:row;border-right:none;border-top:1px solid var(--border);padding:4px 2px;gap:0;z-index:50;background:#0a0e16}
    .logo,.side-foot{display:none}
    .side nav{display:flex;flex-direction:row;width:100%}
    .navlink{flex:1;flex-direction:column;gap:2px;padding:7px 2px;font-size:10px;min-height:48px;align-items:center;justify-content:center;text-align:center}
    .navlink i{font-size:19px}
    .navlink span{font-size:10px;line-height:1.05}
    main{padding:14px 14px 66px;max-width:none}
  }
</style>
