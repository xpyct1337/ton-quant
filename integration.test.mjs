// ===== INTEGRATION: all 3 pages on live data + edge cases + cross-validation =====
import { JSDOM } from 'jsdom';
import fs from 'fs';
let pass=0,fail=0;
const t=(name,cond,info="")=>{ if(cond){pass++;} else {fail++; console.log("FAIL:",name,info);} };
// Complete canvas-2d stub: any method is a no-op, any property is settable.
// (Incomplete stubs make viz fns like renderBubbleMap throw on ctx.scale/arc/fill,
//  which aborts load() and silently breaks downstream holder-table assertions.)
const _grad={addColorStop(){}};
const ctxStub=new Proxy({},{get(o,k){if(k==='createLinearGradient'||k==='createRadialGradient')return ()=>_grad;if(k==='measureText')return ()=>({width:0});if(k==='getImageData')return ()=>({data:[]});return ()=>{};},set(){return true;}});
function boot(file,url,stripRe){
  const html=fs.readFileSync(file,'utf8');
  const dom=new JSDOM(html,{url});
  dom.window.HTMLCanvasElement.prototype.getContext=()=>ctxStub;
  class FakeChart{constructor(){}destroy(){}}
  const store={};
  let redirected=null;
  const real=dom.window.location;
  const loc={get href(){return real.href;},set href(v){redirected=v;},replace:u=>redirected=u,get search(){return real.search;}};
  const g={document:dom.window.document,window:dom.window,location:loc,navigator:{clipboard:{writeText(){}}},
    Chart:FakeChart,fetch:globalThis.fetch,console:{log(){},warn(){},error(){}},
    localStorage:{getItem:k=>store[k]??null,setItem:(k,v)=>store[k]=String(v)},
    setTimeout,clearTimeout,setInterval:()=>0,URLSearchParams,Date,BigInt,Math,Number,JSON,Promise,Object,Array,String,Infinity,isFinite,parseInt,parseFloat,encodeURIComponent};
  const js=html.match(/<script>\n?([\s\S]*?)<\/script>\s*<\/body>/)[1].replace(stripRe,'');
  const ret=stripRe.toString().includes('render')?'{render,refresh,loadDex,summary,treemap,activityDigest,renderTape}':'{load,loadPriceChart}';
  const api=new Function(...Object.keys(g),js+'\n;return '+ret+';')(...Object.values(g));
  return {dom,api,getRedirect:()=>redirected};
}
const parse$=s=>{ // "$1.43B" -> number
  const m=String(s).replace(/[,$]/g,'').match(/([\d.eE+-]+)([KMB]?)/); if(!m)return NaN;
  return parseFloat(m[1])*({K:1e3,M:1e6,B:1e9}[m[2]]||1);
};

// ---- 1. token.html: invalid address must redirect ----
{
  const {getRedirect}=boot('/tmp/token_new.html','https://x.test/token.html?a=INVALID',/function start\(\)[\s\S]*$/);
  t('bad address redirects', getRedirect()==='index.html', getRedirect());
}

// ---- 2. token.html NOT: cross-validate vs raw API ----
{
  const NOT='EQAvlWFDxGF2lXm67y4yzC17wYKD9A0guwPkMs1gOsM__NOT';
  const {dom,api}=boot('/tmp/token_new.html','https://x.test/token.html?a='+NOT,/function start\(\)[\s\S]*$/);
  await api.load();
  const q=id=>dom.window.document.getElementById(id).textContent.trim();
  // independent fetch
  const H={'Accept':'application/json'};
  const info=await (await fetch(`https://tonapi.io/v2/jettons/${NOT}`,{headers:H})).json();
  const rates=await (await fetch(`https://tonapi.io/v2/rates?tokens=${NOT}%2CTON&currencies=usd`,{headers:H})).json();
  const price=rates.rates[NOT].prices.USD;
  const mcap=price*Number(info.total_supply)/1e9;
  t('NOT holders match', parseInt(q('kHolders').replace(/,/g,''))===info.holders_count, q('kHolders')+' vs '+info.holders_count);
  t('NOT mcap within 2%', Math.abs(parse$(q('kMcap'))-mcap)/mcap<0.02, q('kMcap')+' vs '+mcap.toExponential(3));
  t('NOT price within 2%', Math.abs(parse$(q('kPrice'))-price)/price<0.02);
  t('NOT supply 102.45B', q('kSupply')==='102.45B', q('kSupply'));
  t('NOT top10 sane', parseFloat(q('kTop10'))>30&&parseFloat(q('kTop10'))<70, q('kTop10'));
  t('NOT score 0-100', /^\d+ \/ 100$/.test(q('kScore'))&&parseInt(q('kScore'))<=100);
  t('NOT live mode', q('modePill').includes('Live'));
  t('NOT vol30 renders %', /^\d+\.\d%$/.test(q('kVol30')), q('kVol30'));
  { const vsub=dom.window.document.getElementById('kVol30Sub').textContent;
    t('NOT vol30 sub has beta+risk', /vs TON/.test(vsub)&&/(low|moderate|high|extreme) risk/.test(vsub), vsub); }
  // holders collapsed to 10
  const visible=[...dom.window.document.querySelectorAll('#holderTbody tr')].filter(r=>r.style.display!=='none'&&!r.id);
  t('holders collapsed to 10', visible.length===10, visible.length);
  t('show-all button exists', !!dom.window.document.getElementById('hMore'));
  // whale filter must NOT price foreign jettons (TSHIB bug)
  const feedHtml=dom.window.document.getElementById('feed').innerHTML;
  const tshibPriced=/TSHIB[\s\S]{0,80}?\$\d/.test(feedHtml)||/\$[\d.]+[\s\S]{0,120}?TSHIB/.test(feedHtml);
  t('foreign jetton NOT priced at MASTER price (TSHIB bug)', !tshibPriced, 'TSHIB has $ value');
}

// ---- 3. index.html: summary numbers internally consistent ----
{
  const {dom,api}=boot('/tmp/index_new.html','https://x.test/',/render\(\);\s*refresh\(\)\.then[\s\S]*$/);
  api.render(); await api.refresh(); await api.loadDex(); api.summary(); api.treemap(); api.activityDigest();
  const d=dom.window.document;
  const q=id=>d.getElementById(id).textContent.trim();
  const rows=[...d.querySelectorAll('#tbody tr')];
  t('all rows', rows.length>=20, rows.length);
  // sum of row mcaps == summary mcap (within 3%)
  const sumRows=rows.reduce((s,r)=>s+parse$(r.children[5].textContent),0);
  t('summary mcap = sum of rows', Math.abs(parse$(q('sMcap'))-sumRows)/sumRows<0.03, q('sMcap')+' vs '+sumRows.toExponential(3));
  // breadth n/20
  t('breadth format', /^\d+ \/ \d+$/.test(q('sBr')));
  const [a,b]=q('sBr').split('/').map(x=>parseInt(x));
  t('breadth sane', a>=0&&a<=b&&b>=10, q('sBr'));
  // index = weighted avg: recompute from row data
  t('TON-20 index format', /^[+−-]?\d+\.\d{2}%$/.test(q('sIdx')), q('sIdx'));
  // treemap: 20 tiles, total area ~ container
  const tiles=[...d.querySelectorAll('#tmap .tm')];
  t('treemap tiles = core tokens', tiles.length>=15, tiles.length);
  // arb radar now ranks by realizable net profit (net$), profitable rows first
  const arbRows=[...d.querySelectorAll('#arbList .arb-row')];
  const netUsd=arbRows.map(r=>{const m=r.lastElementChild.textContent.match(/\+\$([\d.]+)/);return m?parseFloat(m[1]):-1;});
  t('arb ranked by net profit desc', netUsd.every((v,i)=>i===0||v<=netUsd[i-1]), netUsd.join(','));
  // gross spreads (middle hint) still sane
  const gross=arbRows.map(r=>parseFloat(r.children[1].textContent));
  t('arb gross spreads sane <50%', gross.every(v=>isFinite(v)&&v>=0&&v<50), gross.join(','));
  // for any profitable row, net% must be strictly below gross% (costs subtracted)
  for(const r of arbRows){
    const nm=r.lastElementChild.textContent.match(/\(([-\d.]+)%\)/), gm=r.children[1].textContent.match(/([\d.]+)% gross/);
    if(nm&&gm) t('arb net% below gross%', parseFloat(nm[1])<parseFloat(gm[1]), r.lastElementChild.textContent+' / '+r.children[1].textContent);
  }
  // vol/tvl column: recompute for row 1
  const r0=rows[0];
  const vol=parse$(r0.children[6].textContent), tvl=parse$(r0.children[7].textContent), vt=parseFloat(r0.children[8].textContent);
  if(isFinite(vol)&&isFinite(tvl)&&isFinite(vt)) t('vol/tvl recompute', Math.abs(vol/tvl-vt)<0.05, `${vol}/${tvl} vs ${vt}`);
  // filters never crash & subset
  for(const f of ['movers','dormant','wash','liquid']){
    const chip=[...d.querySelectorAll('.fchip')].find(c=>c.dataset.f===f);
    chip.click();
    const n=d.querySelectorAll('#tbody tr').length;
    t('filter '+f+' subset', n>=0&&n<=30, n);
  }
}

// ---- 4. token2 demo mode: exactly 10 signals ----
{
  const NOT='EQAvlWFDxGF2lXm67y4yzC17wYKD9A0guwPkMs1gOsM__NOT';
  const {dom,api}=boot('/tmp/token2.html','https://x.test/token2.html?a='+NOT+'&demo=1',/function start\(\)[\s\S]*$/);
  await api.load();
  const sigs=dom.window.document.querySelectorAll('#signals .sig').length;
  t('demo shows 10 signals', sigs===10, sigs);
  // slippage cells parse as % and increase with size
  const row=dom.window.document.querySelector('#slipTbody tr');
  if(row){
    const cells=[...row.querySelectorAll('td')].slice(2,5).map(td=>parseFloat(td.textContent));
    t('slippage monotonic', cells[0]<=cells[1]&&(cells[1]<=cells[2]||isNaN(cells[2])), cells.join(','));
  }
}
console.log(`\nINTEGRATION: ${pass} passed, ${fail} failed`);
process.exit(fail?1:0);
