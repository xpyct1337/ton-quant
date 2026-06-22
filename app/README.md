# TON Quant v2 (SvelteKit)

New main page (Markets) — bento overview + agent feed + supply pressure + jetton table.
Builds to static, deployed to GitHub Pages via `.github/workflows/deploy.yml`.

## Local preview
    cd app && npm install && npm run dev      # http://localhost:5173/ton-quant/

## Build / test
    npm run build      # -> app/build (BASE_PATH defaults to /ton-quant)
    npm test           # node:test, pure-fn checks

Data is fetched client-side at runtime from raw.githubusercontent (snapshots/signals)
+ one batched TONAPI rates call (live price overlay). No backend, no rebuild on data changes.
