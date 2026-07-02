# TON Quant

Analytics for the TON ecosystem: markets, screener, token deep-dives, smart-money
wallets, paper bots, momentum forward-test and an AI smart-money desk.

- Site: SvelteKit static build in `app/` (deployed to GitHub Pages by `deploy.yml`)
- Data: daily GitHub Actions collectors (`scripts/*.py` → `data/*.json`), an intraday
  slice at 15:10 UTC, plus a 24/7 M1 desk worker writing `data/desk/`
- Live layer: pages overlay live TONAPI prices every 60s on top of the baked
  snapshots; percent-changes are re-based so price and change always agree
- APIs: [TONAPI.io](https://tonapi.io), DexScreener, [STON.fi](https://api.ston.fi),
  GeckoTerminal — public endpoints, fetched client-side

Not financial advice.
