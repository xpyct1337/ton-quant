# TON Quant v3.0 — AI Smart-Money Desk (роадмап)

Версия v3.0: поверх v2 (сбор данных в GitHub Actions + сайт SvelteKit) встаёт слой
локальных LLM-агентов на M1 Mac — манипуляция-устойчивый, обоснованный copy-фид.
Спек: `docs/V3.0-AI-SMART-MONEY-DESK.md`. Альфа (evolve-run #1–#45) заархивирована в
`ROADMAP-alpha-archive.md`.

Архитектура (три слоя, связь только через файлы в репо):
`[Сбор] GitHub Actions → data/*.json` · `[Десk] M1 launchd → data/desk/verdicts.json` ·
`[Витрина] SvelteKit статика → читает verdicts.json`.

---

## 🚀 Готово 28.06.2026 — запуск деска на Mac (MVP, Phase 1)

**AI Smart-Money Desk поднят и прогнан на живых данных на MacBook Air M1 (8 ГБ).**
Перенос v3.0 со спека в работающий рантайм. Сбор данных остаётся в облаке (Actions),
деск читает закоммиченные `data/` и пишет вердикты обратно в репо.

**Рантайм.** Ollama (Metal) + `qwen3:4b` (основная, ~2.5 ГБ) и `gemma3:4b` (альт).
Под 8 ГБ: `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`. Оба отдают валидный
JSON через `/api/generate` (`format:json`, `think:false`); qwen3 ~7 с/вызов.

**Детерминированный слой фич (`scripts/desk_features.py`).** На roster-кошелёк/токен
из существующих `data/` (без новых фетчей): `wash` (переиспользует ban-лист
wash-детектора), `co_entry` (координация входа из диффов `data/wallets/<date>.json`),
`vol_auth` (аутентичность объёма: vol24/TVL + перекос buys/sells), `conc`
(концентрация холдеров — MVP-прокси по числу холдеров; реальный top10/HHI = Phase 2),
`edge_dispersion`. Все нормированы 0..1, self-check на живом срезе.

**Агенты (`scripts/desk.py`).** Клиент Ollama (urllib, таймаут+retry) + агент-1
«манипуляция» (`{manip_risk,flags,reason}`) + агент-2 «вёттинг»
(`{copy_ok,conviction,reason}`). Идут последовательно (одна модель в памяти),
отказоустойчиво (битый LLM-вызов → детерминированный floor, прогон не падает).
Детерминированные пороги — жёсткий гейт (wash-ban → high; high → `copy_ok=false`),
LLM только синтезирует обоснование и может поднять риск, но не опустить ниже floor.

**Проверка (`scripts/desk_test.py`, §10, на реальных данных).** Прогон деска на живом
`data/` → схема `verdicts.json` валидна; все wash-баненные токены (`data/paper/bots.json`
→ `wash_ban`) получают `manip_risk: high`; ни один high-risk кошелёк не `copy_ok`.

**Оркестрация.** `scripts/desk_run.sh` (pull → ensure Ollama → desk → commit/push) +
launchd `com.tonquant.desk` (ночь 03:30 + `RunAtLoad` catch-up). Гайд:
`docs/DESK-SETUP-m1.md`.

**Следующее:** D — витрина `/wallets` (`loadVerdicts()` + риск-значок/CoT-тултип/сортировка
грязных); полный ночной прогон всего ростера; Phase 2 — агент-ресёрчер альф под CPCV/PBO
и глубокая on-chain форензика (transfer-таймлайн → настоящий бандлер/снайпер-детект).
