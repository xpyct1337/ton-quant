// ===== NAV/LINK GUARD: every page must be clean and link only to real files =====
// Guards against (a) NUL-byte corruption from the mount, (b) dead local hrefs
// (e.g. the main-page.html bug). Run from repo root: node nav.test.mjs
import fs from 'fs';
let pass=0,fail=0;
const t=(name,cond,info="")=>{ if(cond){pass++;} else {fail++; console.log("FAIL:",name,info);} };
const DIR=process.env.TQ_DIR||'.';
const pages=fs.readdirSync(DIR).filter(f=>f.endsWith('.html')&&f!=='index.html'); // index.html is provided by the SvelteKit build
t('found html pages', pages.length>=5, pages.length);
const exists=new Set(pages); exists.add('index.html'); // provided by SvelteKit build
for(const p of pages){
  const buf=fs.readFileSync(DIR+'/'+p);
  // (a) no NUL bytes
  t(`${p}: no NUL bytes`, !buf.includes(0), 'nuls='+buf.filter(b=>b===0).length);
  const html=buf.toString('utf8');
  // (b) ends with </html>
  t(`${p}: ends with </html>`, /<\/html>\s*$/.test(html));
  // (c) every local .html href points to a file that exists
  const hrefs=[...html.matchAll(/href="([^"]+\.html)(?:\?[^"]*)?"/g)].map(m=>m[1]);
  const dead=[...new Set(hrefs)].filter(h=>!/^https?:\/\//.test(h)&&!exists.has(h.split('/').pop()));
  t(`${p}: no dead local html links`, dead.length===0, dead.join(','));
}
console.log(`\nNAV: ${pass} passed, ${fail} failed`);
process.exit(fail?1:0);
