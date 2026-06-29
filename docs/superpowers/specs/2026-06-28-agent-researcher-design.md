# Агент-ресёрчер — авто-промоушен факторов (дизайн, Phase 2)

Дата: 2026-06-28 · Статус: одобрен к реализации (Igor, 28.06) · Версия: v3.0 Phase 2
Контекст: [[2026-06-28-desk-worker-24-7-design]] (движок), [[V3.0-AI-SMART-MONEY-DESK]] (спек),
переиспользует калибровку (`desk_calibration.py`) и forward-логику (`score.py`).

## 1. Цель

Самое «развитие»: LLM 24/7 предлагает кандидат-факторы, детерминированный харнесс считает их
forward-доходность под walk-forward/OOS-гейтом (дисциплина CPCV/PBO/DSR), выжившие
**авто-вливаются** в расчёт деска — с полной историей правок и жёсткими предохранителями,
чтобы человек мог отредактировать/откатить стратегию. Scope — **токен-факторы** (есть forward
ground truth); кошельки вне фазы (нет исторических roster-метрик).

## 2. Фактор = безопасный DSL (НЕ исполняемый код)

LLM выдаёт JSON-спек; Python интерпретирует дерево выражения (whitelist, **без eval/exec**):

```jsonc
{ "id": "f_voltvl",
  "expr": {"op": "div", "a": "vol24", "b": "tvl"},     // a/b могут быть полем, числом или под-expr
  "direction": "high_is_bad",                           // high signal => higher manip risk
  "threshold": 3.0,                                      // фактор «срабатывает» выше порога
  "horizon": 7 }
```

- Поля (whitelist): `vol24, tvl, holders, buys, sells, mcap, supply, price, pools`,
  производные `buy_sell_skew` (=|buys-sells|/(buys+sells)), `vol_tvl` (=vol24/tvl).
- Операции (whitelist): `div, mul, sub, add, abs, min, max, const`.
- Интерпретатор `eval_expr(expr, fields)` обходит дерево рекурсивно; неизвестное поле/op или
  деление на 0 → фактор невалиден (отказ, не падение). Деление на 0 → 0.

## 3. Гейт (walk-forward OOS + анти-оверфит)

Сигнал считается по всем `data/snapshots/*`; даты делятся **in-sample (старые 60%) / OOS
(новые 40%)**. Для токенов, где фактор «срабатывает» (signal > threshold по `direction`),
берём forward EXCESS-доходность на `horizon` (та же мера, что в `desk_calibration`).

Проходит только если **все**:
- in-sample: средняя forward-excess у «сработавших» значимо отрицательна (`direction=high_is_bad`)
  — Wilson-LB нижняя граница доли убыточных > 0.5 И sign-test p < bar;
- OOS: тот же знак И значимость (PBO-страховка — не переобучено на in-sample);
- **deflated bar (анти data-mining):** держим `trials` (сколько факторов LLM перебрал);
  требуем `p < BASE_P / sqrt(max(trials,1))` — чем больше попыток, тем строже планка (DSR-идея).

Статистика (Wilson-LB, sign-test) переиспользуется из `score.py`.

## 4. Авто-промоушен + история + правка

- `data/desk/factors_active.json` — активные факторы (кап **MAX_ACTIVE=8**): спеки + их
  gate-метрики + ts промоушена.
- `data/desk/factors_history.json` — **append-only аудит**:
  `{ts, action: proposed|promoted|rejected|demoted|disabled, factor, metrics, reason}`.
  Каждое авто-действие пишется сюда; правки человека — тоже (`--note`).
- **Промоут:** фактор прошёл гейт И не дублирует активный (по expr) И есть слот (или вытесняет
  слабейший, если строго лучше) → добавить в active, лог `promoted`.
- **Авто-демоушен:** периодический `revalidate` пере-прогоняет активные на свежем OOS; просел
  ниже планки → снять, лог `demoted`. Набор остаётся честным.
- **Human-override:** правишь `factors_active.json` напрямую или
  `python3 scripts/desk_factors.py --disable <id> [--note "..."]` (пишет в history). Откат =
  убрать из active (история объясняет что/почему было).

## 5. Предохранители (торгово-смежная логика)

- **Floors жёсткие и неперебиваемые:** wash-ban → `high` всегда. Активный фактор может только
  **поднять** риск/добавить флаг, **никогда не опустить ниже floor** — выученный фактор не
  «разбанит» washed-токен. Реализация: итоговый риск = `max(floor_risk, factor_risk)`.
- Кап активных, deflated-bar, авто-демоушен, полный аудит, лёгкий human-disable.

## 6. Где крутится

Новые task-раннеры в `desk_worker.py`, **низший приоритет (idle-filler)** под тем же
термо/энерго-governor:
- `research` — один проход: LLM предлагает 1 фактор → гейт → промоут/реджект (лог).
- `revalidate` — реже (раз в ~12ч): пере-валидация активных, авто-демоушен.

Picker-приоритет: `daily_verdicts` → `calibrate` → `deep_vetting` → `research` → (по таймеру)
`revalidate`. Ресёрчер ест только свободные циклы.

## 7. Интеграция в деск

- `desk_factors.py`: `eval_expr`, `factor_signal(spec, fields)`, `apply_active(fields) ->
  (risk_level, flags)` (читает `factors_active.json`).
- `desk.py` `agent1` для токенов: после floor — `factor_risk = apply_active(token_fields)`;
  итог `manip_risk = max(floor, factor_risk, llm)`; флаги активных факторов добавляются.
- Токен-фичи должны нести сырые snapshot-поля для факторов: `desk_features` добавляет в
  токен-словарь блок `fields` (сырой snapshot-объект токена).

## 8. Файлы

- Create `scripts/desk_factors.py` (+ `_test.py`) — DSL-интерпретатор, registry, apply, CLI.
- Create `scripts/desk_researcher.py` (+ `_test.py`) — propose (LLM) → gate (OOS) → promote.
- Modify `scripts/desk_worker.py` — task-раннеры `research`/`revalidate` + picker.
- Modify `scripts/desk.py` — применять активные факторы в токен-вердиктах.
- Modify `scripts/desk_features.py` — класть сырые `fields` в токен-словарь.

## 9. Тесты

- DSL: `eval_expr` считает дерево; чужое поле/op/деление-на-0 → невалидно (не падает).
- Гейт: синтетический фактор с зашитым отрицательным forward-эффектом проходит in-sample+OOS;
  чисто-шумовой фактор валится на OOS; рост `trials` поднимает планку.
- Registry: промоут добавляет+логирует; кап вытесняет слабейшего; демоут снимает+логирует;
  `--disable` пишет в history.
- Безопасность: `max(floor, factor)` — активный фактор НЕ опускает wash-ban ниже `high`.

## 10. Вне scope (YAGNI)

- Кошельковые факторы (нет исторического roster-edge) — позже.
- Новые on-chain фетчи (форензика) — отдельный спек.
- Многооперандные/временные (lag/rolling) факторы — v2 DSL, если простые исчерпаются.
- Авто-сайзинг paper-бота по факторам — Phase 3.
