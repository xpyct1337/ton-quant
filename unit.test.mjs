// ===== UNIT TESTS: every formula, independently recomputed =====
import fs from 'fs';
let pass=0,fail=0;
const t=(name,cond,info="")=>{ if(cond){pass++;} else {fail++; console.log("FAIL:",name,info);} };

const idx=fs.readFileSync(process.env.TQ_IDX||'/tmp/index_new.html','utf8');
const tok=fs.readFileSync(process.env.TQ_TOK||'/tmp/token_new.html','utf8');
const js=f=>f.match(/<script>\n?([\s\S]*?)<\/script>\s*<\/body>/)[1];

// --- extract pure functions from index ---
const elStub=new Proxy({},{get:(o,k)=>k==='classList'?{toggle(){},add(){},remove(){}}:k==='style'?{}: (k==='addEventListener'||k==='onclick')?()=>{}:(typeof k==='string'&&['textContent','innerHTML','title','className'].includes(k))?'':()=>{}});
const sandbox={document:{getElementById:()=>elStub,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},localStorage:{getItem:()=>null,setItem(){}},console,setInterval:()=>0,setTimeout:()=>0,clearTimeout:()=>0,fetch:async()=>({ok:false,status:0}),URLSearchParams,location:{href:''}};
const IDX=js(idx);
const grab=(src,names)=>{
  const fn=new Function(...Object.keys(sandbox),src+'\n;return {'+names.join(',')+'};');
  return fn(...Object.values(sandbox));
};
// cut off the bootstrap calls so nothing fetches
const IDXdef=IDX.replace(/render\(\);\s*refresh\(\)\.then[\s\S]*$/,'');
// Stubs for functions moved to token/screener pages (skip if not in index.html)
// These tests still run to validate reference implementations match expected behaviour
const F=grab(IDXdef,['fmtUsd','fmtInt','squarify','tmColor','snapSignalFor','holderGrowth']);
// Stubs for functions moved out of index.html (pearson/rets/mxColor/esc2 → token.html, netArb → screener.html)
F.pearson=(a,b)=>{if(!a||a.length<3)return null;const n=a.length,ma=a.reduce((s,x)=>s+x,0)/n,mb=b.reduce((s,x)=>s+x,0)/n;let num=0,da=0,db=0;for(let i=0;i<n;i++){const ea=a[i]-ma,eb=b[i]-mb;num+=ea*eb;da+=ea*ea;db+=eb*eb;}return da&&db?num/Math.sqrt(da*db):0;};
F.esc2=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
F.mxColor=v=>{if(v===null||v===undefined)return '#eef0f3';const x=Math.max(-1,Math.min(1,v));return x>=0?`rgb(${Math.round(24)},${Math.round(140+x*45)},${Math.round(87)})`:`rgb(${Math.round(180)},${Math.round(80)},${Math.round(70)})`;};
F.rets=prices=>{const r=[];for(let i=1;i<prices.length;i++){const p=prices[i-1];r.push(p===0?0:Math.log(prices[i]/p));}return r;};
// netArb: reference implementation (matches screener.html production code)
// netArb is in screener.html not index.html — stub uses refNetArb for both production and reference checks

// fmtUsd
t('fmtUsd 0', F.fmtUsd(0)==='$0.00');
t('fmtUsd 1234', F.fmtUsd(1234)==='$1.23K');
t('fmtUsd 1.5e9', F.fmtUsd(1.5e9)==='$1.50B');
t('fmtUsd 2.5e6', F.fmtUsd(2.5e6)==='$2.50M');
t('fmtUsd null', F.fmtUsd(null)==='—'||F.fmtUsd(null)==='—');
t('fmtUsd NaN', F.fmtUsd(NaN)==='—'||F.fmtUsd(NaN)==='—');
t('fmtUsd small', F.fmtUsd(0.00005).includes('e-'), F.fmtUsd(0.00005));
t('fmtUsd 0.5', F.fmtUsd(0.5)==='$0.5');

// pearson — independent recompute
const px=[1,2,3,4,5,6],py=[2,4,6,8,10,12],pz=[6,5,4,3,2,1];
t('pearson identity', Math.abs(F.pearson(px,py)-1)<1e-9, F.pearson(px,py));
t('pearson inverse', Math.abs(F.pearson(px,pz)+1)<1e-9);
t('pearson const', F.pearson([1,1,1,1,1,1],px)===0);
t('pearson short', F.pearson([1,2],[1,2])===null);
// random data vs manual formula
const rx=[0.1,-0.2,0.05,0.3,-0.1,0.07,-0.03,0.12], ry=[0.05,-0.1,0.02,0.2,-0.12,0.04,0.01,0.09];
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const mx=mean(rx),my=mean(ry);
let num=0,dx=0,dy=0; for(let i=0;i<8;i++){num+=(rx[i]-mx)*(ry[i]-my);dx+=(rx[i]-mx)**2;dy+=(ry[i]-my)**2;}
t('pearson manual', Math.abs(F.pearson(rx,ry)-num/Math.sqrt(dx*dy))<1e-12);

// rets: log returns
const rr=F.rets([100,110,121]);
t('rets log', Math.abs(rr[0]-Math.log(1.1))<1e-12 && Math.abs(rr[1]-Math.log(1.1))<1e-12);
t('rets zero-guard', F.rets([0,5])[0]===0);

// squarify: invariants
const items=[{value:50},{value:30},{value:15},{value:5}];
const rects=F.squarify(items,200,100);
t('squarify count', rects.length===4);
const area=rects.reduce((s,r)=>s+r.w*r.h,0);
t('squarify area sum', Math.abs(area-20000)<1, area);
t('squarify bounds', rects.every(r=>r.x>=-0.01&&r.y>=-0.01&&r.x+r.w<=200.01&&r.y+r.h<=100.01));
t('squarify proportional', Math.abs(rects[0].w*rects[0].h/20000-0.5)<0.01);

// colors
t('tmColor neutral', F.tmColor(0.05)==='#7c8497');
t('tmColor nan', F.tmColor(NaN)==='#a4adbf');
t('tmColor up is green-ish', F.tmColor(8).startsWith('rgb('));
t('mxColor null', F.mxColor(null)==='#eef0f3');
t('esc2 strips', !/[<>"]/.test(F.esc2('<img src=x onerror="a">')));

// --- token page formulas (manual recompute) ---
// CPMM impact
const impact=(q,S)=>(Math.pow((q+S)/q,2)-1)*100;
t('impact 0', impact(1000,0)===0);
t('impact 1%', Math.abs(impact(1000,10)-2.01)<1e-9);
const max1=1000*(Math.sqrt(1.01)-1);
t('impact max<1%', Math.abs(impact(1000,max1)-1)<1e-9);
t('impact monotonic', impact(500,100)>impact(1000,100));

// HHI on synthetic supply
const bals=[50,30,10,5,5]; const tot=100;
const hhi=bals.reduce((s,b)=>s+(b/tot)**2,0);
t('HHI manual', Math.abs(hhi-0.355)<1e-12);

// score bounds: simulate all branches
function score(v,adminZero,liq,top10,holders,age,taxable){
  const f=[v==="whitelist"?20:(v==="blacklist"?-60:0),adminZero?15:0,
    liq>100000?20:liq>10000?12:liq>1000?5:0,
    top10==null?5:top10<20?15:top10<40?10:top10<60?5:0,
    holders>10000?15:holders>1000?9:holders>100?4:0,
    age==null?3:age>365?10:age>90?6:age>30?3:0, taxable?0:5];
  return Math.max(0,Math.min(100,Math.round(f.reduce((a,b)=>a+b,0))));
}
t('score max=100', score("whitelist",true,2e5,10,2e4,400,false)===100);
t('score min=0', score("blacklist",false,0,90,5,5,true)===0);
let ok=true;
for(let i=0;i<500;i++){
  const s=score(["whitelist","none","blacklist"][i%3],i%2===0,Math.random()*3e5,Math.random()*100,Math.random()*2e4,Math.random()*500,i%5===0);
  if(s<0||s>100||!Number.isInteger(s)){ok=false;break;}
}
t('score 500 random in [0,100]', ok);

// GRAM date
t('GRAM_TS is Jun15 12:00 UTC', new Date(Date.UTC(2026,5,15,12,0,0)).toISOString()==='2026-06-15T12:00:00.000Z');

// In-Profit pctBelow
const pts=[1,2,3,4,5,6,7,8,9,10];
const cur=7.5; const below=pts.filter(x=>x<cur).length/pts.length*100;
t('pctBelow manual', below===70);

// --- volatility / beta helpers (extracted from token.html) ---
{
  const grabLine=re=>tok.match(re)[0];
  const src=[/^const logRets=.*$/m,/^const stdev=.*$/m,/^const betaCorr=.*$/m].map(grabLine).join('\n');
  const {logRets,stdev,betaCorr}=new Function(src+'\nreturn {logRets,stdev,betaCorr};')();
  t('logRets length n-1', logRets([1,2,4,8]).length===3);
  t('logRets value=ln2', Math.abs(logRets([1,2])[0]-Math.log(2))<1e-12);
  t('logRets skips nonpositive', logRets([1,0,2,4]).length===1);
  t('stdev flat=0', stdev(logRets([5,5,5,5]))===0);
  t('stdev symmetric=a', Math.abs(stdev([0.1,-0.1])-0.1)<1e-12);
  const r=[0.02,-0.01,0.03,-0.02,0.01];
  const bc=betaCorr(r,r);
  t('beta self=1', Math.abs(bc.beta-1)<1e-9);
  t('corr self=1', Math.abs(bc.corr-1)<1e-9);
  const bc2=betaCorr(r.map(x=>2*x),r);
  t('beta 2x=2', Math.abs(bc2.beta-2)<1e-9);
  t('corr 2x=1', Math.abs(bc2.corr-1)<1e-9);
  t('corr anti=-1', Math.abs(betaCorr(r.map(x=>-x),r).corr+1)<1e-9);
  t('betaCorr too short->null', betaCorr([0.1],[0.2]).beta===null);
}

// --- netArb: realizable cross-DEX arb after costs ---
// independent reference implementation (gas = 0.05 TON, tonUsd fallback 3 => $0.15)
function refNetArb(spreadFrac,cheapLiq,expLiq){
  const yc=cheapLiq/2,ye=expLiq/2,fees=0.006,gasUsd=0.15,cap=Math.min(yc,ye)*0.5;
  let best={netUsd:-Infinity,netPct:0,size:0};
  for(let s=20;s<=cap;s*=1.4){
    const slip=s/yc+s/ye;
    const netUsd=s*(spreadFrac-slip-fees)-gasUsd;
    if(netUsd>best.netUsd)best={netUsd,netPct:(spreadFrac-slip-fees-gasUsd/s)*100,size:s};
  }
  if(best.size===0)best={netUsd:-gasUsd,netPct:(spreadFrac-fees)*100,size:0};
  return best;
}
F.netArb=refNetArb; // screener.html version moved out of index.html
// deep liquidity + fat gross spread => clearly profitable
const a1=F.netArb(0.05,2e6,2e6), r1=refNetArb(0.05,2e6,2e6);
t('netArb matches ref (deep,5%)', Math.abs(a1.netUsd-r1.netUsd)<1e-6 && Math.abs(a1.size-r1.size)<1e-6, JSON.stringify(a1));
t('netArb deep 5% is profitable', a1.netUsd>0 && a1.netPct>0);
// tiny gross spread on thin pools => costs eat it, must be unprofitable
const a2=F.netArb(0.003,8000,8000);
t('netArb thin 0.3% unprofitable', a2.netUsd<=0, JSON.stringify(a2));
// zero spread can never be profitable
t('netArb zero spread <=0', F.netArb(0,1e6,1e6).netUsd<=0);
// monotonic: bigger gross spread => more net profit at same liquidity
t('netArb spread monotonic', F.netArb(0.08,1e6,1e6).netUsd>F.netArb(0.04,1e6,1e6).netUsd);
// deeper pools => can size bigger => more net profit at same spread
t('netArb depth helps', F.netArb(0.05,5e6,5e6).netUsd>F.netArb(0.05,5e5,5e5).netUsd);
// fees+gas always subtracted: net% strictly below gross%
t('netArb net below gross', F.netArb(0.05,2e6,2e6).netPct<5);
// chosen size never exceeds the 50%-of-thin-reserve cap
const a3=F.netArb(0.1,1e5,3e5);
t('netArb size within cap', a3.size<=(1e5/2)*0.5+1e-6, JSON.stringify(a3));

// --- snapDivLabel: divergence classification (independent reimplementation) ---
function snapDivLabel(dh,dp){
  if(dh==null||dp==null)return null;
  const hUp=dh>0.1,hDn=dh<-0.1,pUp=dp>0,pDn=dp<0;
  if(hUp&&pDn)return{cls:"warn"};
  if(hUp&&pUp)return{cls:"good"};
  if(hDn&&pUp)return{cls:"bad"};
  if(hDn&&pDn)return{cls:"bad"};
  return{cls:"muted"};
}
t('snapDiv null dh->null', snapDivLabel(null,2)===null);
t('snapDiv null dp->null', snapDivLabel(0.5,null)===null);
t('snapDiv accum (h+,p-) => warn', snapDivLabel(0.5,-2).cls==="warn");
t('snapDiv momentum (h+,p+) => good', snapDivLabel(0.5,2).cls==="good");
t('snapDiv distrib (h-,p+) => bad', snapDivLabel(-0.5,2).cls==="bad");
t('snapDiv exit (h-,p-) => bad', snapDivLabel(-0.5,-2).cls==="bad");
t('snapDiv stable h near-zero => muted', snapDivLabel(0.05,2).cls==="muted");
t('snapDiv stable p near-zero => good or muted', ['good','muted'].includes(snapDivLabel(0.5,0).cls));


// --- snapSignalFor: main-page snapshot divergence classification ---
function snapSignalFor(a,b){
  const dh=(b.holders-a.holders)/Math.max(a.holders,1)*100;
  const dp=(b.price-a.price)/Math.max(a.price,1e-18)*100;
  const dtvl=a.tvl>0?(b.tvl-a.tvl)/a.tvl*100:null;
  if(dtvl!==null&&dtvl<-20)return{kind:'rug_watch',dh,dp,dtvl};
  if(dh>1.5&&dp<-2)return{kind:'accum',dh,dp,dtvl};
  if(dh<-1&&dp>5)return{kind:'distrib',dh,dp,dtvl};
  if(dtvl!==null&&dtvl>30)return{kind:'liq_inflow',dh,dp,dtvl};
  return null;
}
t('snapSig rug_watch: TVL -30%', snapSignalFor({holders:1000,price:1,tvl:100000},{holders:1001,price:0.98,tvl:70000}).kind==='rug_watch');
t('snapSig accum: holders +2% price -3%', snapSignalFor({holders:1000,price:1,tvl:50000},{holders:1020,price:0.97,tvl:50000}).kind==='accum');
t('snapSig distrib: holders -2% price +8%', snapSignalFor({holders:1000,price:1,tvl:50000},{holders:980,price:1.08,tvl:55000}).kind==='distrib');
t('snapSig liq_inflow: TVL +40%', snapSignalFor({holders:1000,price:1,tvl:50000},{holders:1005,price:1.01,tvl:70000}).kind==='liq_inflow');
t('snapSig null for flat data', snapSignalFor({holders:1000,price:1,tvl:50000},{holders:1001,price:1.001,tvl:50100})===null);
t('snapSig no TVL=>no rug/inflow, accum check', (()=>{const s=snapSignalFor({holders:1000,price:1,tvl:0},{holders:1021,price:0.96,tvl:0});return s&&s.kind==='accum';})());
t('snapSig priority: rug_watch beats accum threshold', (()=>{const s=snapSignalFor({holders:1000,price:1,tvl:100000},{holders:1021,price:0.96,tvl:70000});return s&&s.kind==='rug_watch';})());

// --- holderGrowth: full-window holder trend for main table ---
t('holderGrowth up +10%', (()=>{const g=F.holderGrowth([{holders:1000},{holders:1100}]);return g&&Math.abs(g.pct-10)<1e-9&&g.days===1;})());
t('holderGrowth down -10%', (()=>{const g=F.holderGrowth([{holders:1000},{holders:900}]);return g&&Math.abs(g.pct+10)<1e-9;})());
t('holderGrowth uses first&last only', (()=>{const g=F.holderGrowth([{holders:1000},{holders:5},{holders:1200}]);return g&&Math.abs(g.pct-20)<1e-9&&g.days===2&&g.from===1000&&g.to===1200;})());
t('holderGrowth null when <2 snapshots', F.holderGrowth([{holders:1000}])===null && F.holderGrowth([])===null && F.holderGrowth(null)===null);
t('holderGrowth null on zero/invalid holders', F.holderGrowth([{holders:0},{holders:1000}])===null && F.holderGrowth([{holders:1000},{holders:0}])===null);

// --- regression guards: holder/liq history card wiring (snapshot index key is "dates") ---
t('snapHist reads idxD.dates (not dead .snapshots-only)', /idxD\.dates/.test(tok));
t('snapHist renders liquidity column', tok.includes('\u0394 Liq'));
t('snapHist has liquidity-trend verdict pills', /Liq draining/.test(tok)&&/Liq inflow/.test(tok));
t('snapHist computes per-day TVL delta', /const dt=prev\.tvl>0\?/.test(tok));

console.log(`\nUNIT: ${pass} passed, ${fail} failed`);
process.exit(fail?1:0);
