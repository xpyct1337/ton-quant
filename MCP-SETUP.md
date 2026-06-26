# TON Quant — MCP / tooling setup

Curated tools to speed up TON Quant dev and surface new alpha. Found via MCP registry + GitHub + 2026 roundups (26.06.2026).

All "local" servers run on **your** machine (where node/python/SSH live), added to Claude Desktop config:
`%APPDATA%\Claude\claude_desktop_config.json` → `mcpServers` block. Restart Claude Desktop after editing.

---

## 1. Context7 — live SvelteKit docs in context

Most-installed MCP (54k★). Injects current SvelteKit/Svelte/Vite docs so code suggestions stop being stale. Biggest immediate win for the v2 redesign.

```json
"context7": {
  "command": "npx",
  "args": ["-y", "@upstash/context7-mcp"]
}
```

Then prompt: *"use context7"* and ask SvelteKit questions. No API key needed for basic use.
Repo: https://github.com/upstash/context7

---

## 2. DEX data MCPs (free, feed the dashboards)

### DEX K-line (GeckoTerminal) — OHLCV candles per pool
Auto-picks highest-liquidity pool. Free, no auth. Good for STON.fi/DeDust pool charts + backtest bars.
```bash
git clone https://github.com/kukapay/dex-kline-mcp.git && cd dex-kline-mcp
uv sync
uv run mcp install main.py --name "DEX K-line"
```
Tool: `get_kline(chain, address, timeframe, limit)`. Note: chains are `eth`/`bsc`/`solana` — **no native TON chain**, so use this for cross-chain reference, not TON pools.

### DexScreener — real-time pair/token stats (supports TON)
```bash
curl -L https://raw.githubusercontent.com/opensvm/dexscreener-mcp-server/main/install.sh | bash
```
Tools: `search_pairs`, `get_pairs_by_token_addresses`, `get_pairs_by_chain_and_address` (use `chainId: "ton"`).
Repo: https://github.com/opensvm/dexscreener-mcp-server

### DefiLlama — TVL for TON protocols + token prices
```json
"defillama": {
  "command": "npx",
  "args": ["@mcp-dockmaster/mcp-server-defillama"]
}
```
Tools: `defillama_get_protocol_tvl`, `defillama_get_chain_tvl` (chain `Ton`), `defillama_get_token_prices`.
Repo: https://github.com/dcSpark/mcp-server-defillama

---

## 3. TON-native MCPs

### ton-api-mcp (ton-ai-core) — wraps TONAPI.io, which you already use
Node-based. Cleanest fit since you're on TONAPI already.
```bash
git clone https://github.com/ton-ai-core/ton-api-mcp.git && cd ton-api-mcp
yarn install && yarn build
```
Run (use **your own** TONAPI key from https://tonconsole.com/tonapi):
```bash
npx ton-api-mcp --api-key YOUR_TONAPI_KEY --modules blockchain,accounts,jettons
```
Modules: accounts, blockchain, dns, jettons, nft, staking, wallet.
Repo: https://github.com/ton-ai-core/ton-api-mcp

### ton-blockchain-mcp (devonmojito) — NL queries + trading-pattern analysis
Python. Has `find_hot_trends`, `analyze_trading_patterns`, `get_jetton_price` — directly relevant to copy-trading edge work.
```bash
git clone https://github.com/devonmojito/ton-blockchain-mcp.git && cd ton-blockchain-mcp
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
echo TON_API_KEY=YOUR_TONAPI_KEY > .env
```
Claude config (adjust paths):
```json
"ton-mcp": {
  "command": "C:\\...\\ton-blockchain-mcp\\venv\\Scripts\\python.exe",
  "args": ["-m", "tonmcp.mcp_server"],
  "cwd": "C:\\...\\ton-blockchain-mcp\\src",
  "env": { "PYTHONPATH": "C:\\...\\ton-blockchain-mcp\\src" }
}
```
Repo: https://github.com/devonmojito/ton-blockchain-mcp
⚠️ Beta — don't trust raw numbers from the LLM; verify against TONAPI directly.

---

## 4. Wider findings — possible new approaches (not just MCPs)

These came up searching "wider" and may matter more than any single connector:

**Multi-agent LLM trading frameworks (the big shift in 2026):**
- **TradingAgents** (TauricResearch, ~60k★) — simulates a trading firm: fundamental/sentiment/technical analysts + bull/bear debate + risk manager. Pluggable LLM providers + data vendors (FRED, Polymarket). Architecture worth copying for the signal bot rather than a single-model call. https://github.com/TauricResearch/TradingAgents
- **AI Hedge Fund** (~45k★) — same multi-agent idea, investor-persona agents + risk/portfolio managers. Good reference for structuring signal → position sizing. 

**Better backtest engine than a custom Python harness:**
- **Nautilus Trader** — production-grade, Rust-core, event-driven, same code for backtest + live. If signal_bot.py grows, porting to Nautilus removes look-ahead bias and gives realistic fills. https://github.com/nautechsystems/nautilus_trader

**Derivatives data = your "next: funding/OI features" item:**
- **Coinalyze** — aggregated OI + funding, generous free tier, clean API.
- **FundingPulse** (Apify) — funding/OI/long-short/liquidations from 6 venues incl. Hyperliquid, ~$0.002/symbol.
- **CoinGecko** also exposes perp funding + OI. TON perps are thin, but BTC/ETH funding is a strong meta-filter for the bot.

**TON-specific data you can hit directly (no MCP needed):**
- **STON.fi DEX API** — `/stats` endpoints: TVL, volume, users, trades, per-pool stats, staking. Directly powers dashboard cards. https://docs.ston.fi/developer-section/dex/api/reference
- STON.fi + DeDust now stream to **TradingView** — means standard TV charting/datafeeds are usable for TON pairs.

**Hosted market-data connectors (one-click in Claude, zero local setup)** — if you want them later: CoinGecko, CoinDesk, LunarCrush (social sentiment), Blockscout. Say the word and I wire them up here.

---

## Suggested order
1. Context7 (5 min, instant dev speedup).
2. ton-api-mcp (reuses your TONAPI key).
3. DexScreener + DefiLlama (TON-aware market/TVL data).
4. Evaluate TradingAgents architecture + Coinalyze funding feed for the next bot iteration — likely the highest-ROI items here.
