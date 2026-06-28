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

## 1b. 24/7 worker (основной режим)

`scripts/desk_worker.py` (launchd `com.tonquant.worker`, KeepAlive) работает
непрерывно: журналирует дневные вердикты (`data/desk/verdicts/<date>.json`),
deep-вётит сущности ансамблем (чтобы модель не простаивала) и само-калибруется
(`data/desk/calibration.json`) — под термо/энерго-governor (тяжёлая работа только от
сети, бэк-офф при троттлинге). Коммитит **только** `data/desk/` батчами (~30 мин),
`pull --rebase` + ретрай → не дерётся с Actions(облако)/PC. Каждый шаг толерантен —
цикл не падает, KeepAlive поднимает после краша. Заменяет ночной `com.tonquant.desk`
(оставлен выгруженным как fallback).

```sh
launchctl load   ~/Library/LaunchAgents/com.tonquant.worker.plist   # запустить 24/7
launchctl unload ~/Library/LaunchAgents/com.tonquant.worker.plist   # остановить
tail -f ~/Library/Logs/tonquant-worker.log                          # смотреть
python3 scripts/desk_worker.py --once                               # один проход (отладка)
python3 scripts/desk_calibration.py --check                         # self-test калибровки
```

## 2. Ночной режим (fallback `com.tonquant.desk`)

Старый plist `~/Library/LaunchAgents/com.tonquant.desk.plist` (`desk_run.sh`: pull →
ensure Osaurus → `desk.py` → commit/push) оставлен **выгруженным** как запасной
одноразовый ночной прогон. Грузить только если 24/7-worker не используется:

```sh
launchctl load ~/Library/LaunchAgents/com.tonquant.desk.plist
launchctl list | grep tonquant
```

## 3. Мониторинг

```sh
tail -f ~/Library/Logs/tonquant-worker.log       # лог 24/7-воркера (основной)
osaurus status                                    # сервер Osaurus (:1337) жив?
osaurus list                                      # какие MLX-модели скачаны
cat ~/Projects/ton-quant/data/desk/verdicts.json     # последние вердикты
cat ~/Projects/ton-quant/data/desk/calibration.json  # правота сигнала (forward-исходы)
launchctl list com.tonquant.worker               # статус воркера / последний exit-код
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
