# DESK-SETUP-m1 — AI Smart-Money Desk на MacBook Air M1 (8 ГБ)

Как поднять и обслуживать деск v3.0 на Mac. Сбор данных живёт в GitHub Actions
(облако) — деск его не трогает: он читает закоммиченные `data/` и пишет
`data/desk/verdicts.json` обратно в репо. Спек: `docs/V3.0-AI-SMART-MONEY-DESK.md`.

## 0. Что уже сделано на этом Mac (28.06.2026)

- **Бэкенд LLM: Osaurus** (нативный Apple-MLX, сервер на `:1337`), модель
  **`qwen3-4b-4bit`**. MLX быстрее/легче Ollama на M1 и отдаёт чистый JSON через
  OpenAI-совместимый `/v1/chat/completions` (`response_format: json_object`, `/no_think`).
  Ollama тоже стоит (`qwen3:4b`/`gemma3:4b`, `:11434`) как запасной бэкенд.
- Бэкенд/модель меняются в `data/desk/config.json` (`endpoint`, `model`) без правки кода.
- SSH-ключ `~/.ssh/id_ed25519` (в keychain) добавлен на GitHub → clone/push работают.
- Репо: `~/Projects/ton-quant`. Python 3.11 (stdlib + urllib, без зависимостей).
- launchd-агент `com.tonquant.desk` (ночь 03:30 + RunAtLoad catch-up).

## 1. Ручной прогон

```sh
cd ~/Projects/ton-quant
git pull
python3 scripts/desk_features.py --check   # self-check фич (0..1, wash_ban)
python3 scripts/desk.py                     # полный прогон (весь ростер ~15 мин)
python3 scripts/desk_test.py                # ассерты §10 на verdicts.json
```

Ограничить ростер (быстрый прогон / слабая ночь): `DESK_LIMIT=10 python3 scripts/desk.py`
или поле `wallet_limit` в `data/desk/config.json`. Сменить модель: `DESK_MODEL=gemma3:4b`
или `model` в конфиге.

`data/desk/config.json` (бэкенд/модель/лимит; читается и сайтом-пультом `/desk`):

```json
{ "backend": "osaurus",
  "endpoint": "http://localhost:1337/v1/chat/completions",
  "model": "qwen3-4b-4bit",
  "wallet_limit": null }
```

Переключить на Ollama: `"endpoint":"http://localhost:11434/v1/chat/completions"`,
`"model":"qwen3:4b"` (или env `DESK_ENDPOINT` / `DESK_MODEL`).

## 2. launchd (ночной прогон + catch-up)

Plist лежит в `~/Library/LaunchAgents/com.tonquant.desk.plist`. Запускает
`scripts/desk_run.sh`: pull → поднять Ollama если не запущен → `desk.py` →
`git add/commit/push data/desk/`. Никогда не падает (каждый шаг толерантен к ошибке).

```sh
# загрузить (один раз; и после правок plist — выгрузить, затем загрузить)
launchctl unload ~/Library/LaunchAgents/com.tonquant.desk.plist 2>/dev/null
launchctl load   ~/Library/LaunchAgents/com.tonquant.desk.plist

launchctl list | grep tonquant          # статус (есть в списке = загружен)
launchctl start com.tonquant.desk       # прогнать прямо сейчас (тест)
```

- `RunAtLoad` → деск догоняет пропущенную ночь при первом включении/логине Mac.
- `StartCalendarInterval` 03:30 → ночной батч (Air без кулера — не realtime).

## 3. Мониторинг

```sh
tail -f ~/Library/Logs/tonquant-desk.log         # лог прогонов (pull/desk/push)
osaurus status                                    # сервер Osaurus (:1337) жив?
osaurus list                                      # какие MLX-модели скачаны
cat ~/Projects/ton-quant/data/desk/verdicts.json  # последние вердикты
launchctl list com.tonquant.desk                  # последний exit-код
```

На сайте: страница **`/desk`** (после `deploy.bat`) показывает дату последнего
прогона, модель, число провёченных кошельков и разбивку по риску — читает
`verdicts.json` через `loadDeskStatus()`.

## 4. Типичные проблемы

- **`push failed`** в логе → проверь `ssh -T git@github.com` (должно «successfully
  authenticated»). Вердикты при этом закоммичены локально — Igor синхронизирует.
- **Osaurus не отвечает** → `osaurus serve` (или открой Osaurus.app); проверь
  `curl -s localhost:1337/v1/models`. `desk_run.sh` сам поднимает сервер, если лежит.
- **Memory pressure / своп** → только 4B-модели; уменьшай `wallet_limit`; агенты и так
  идут по одному в памяти.
- **Пустой `/desk`** → деск ещё не пушил `verdicts.json`, либо сайт не передеплоен.
