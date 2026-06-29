# Вётченный copy-trading (дизайн, Phase 3 — рабочий продукт)

Дата: 2026-06-28 · Статус: одобрен (Igor, 28.06) · Версия: v3.0 Phase 3
Контекст: [[V3.0-AI-SMART-MONEY-DESK]], переиспользует `desk_features.first_entries`,
`desk_calibration.forward_excess`. Cloud `paper.py` НЕ трогаем (он в Actions).

## Цель
Операционализировать исходный тезис в track-record: **копировать только вётченных
(`copy_ok`) кошельков выгоднее, чем копировать всех** (лекарство от imitation-penalty).
Две книги head-to-head → доказательство ценности деска (в т.ч. «ценность = сказать НЕТ»).

## Механизм (детерминированный)
- Сигнал копирования = первый вход roster-кошелька в токен (`first_entries()`).
- Исход = `forward_excess(snaps, date, token_addr, HORIZON)` (HORIZON=3; данных мало).
- Книги: `copy_all` (входы всех roster) vs `copy_desk` (только `copy_ok`-кошельки из
  `data/desk/verdicts.json`). Метрики на книгу: n, avg_excess, win_rate, total (Σ excess).
- `edge = copy_desk.avg − copy_all.avg`. Если `copy_desk` пуст (деск вётит всех в NO) →
  `note`: «desk vetoed all; copy_all avg = X (избегнуто)».

## Честная реальность (часть продукта)
Датированные `wallets/<date>.json` ~5 дней + `copy_ok` сейчас у всех false → `copy_desk`
почти пуст. Это и есть демо: наивное копирование лузер-ростера теряет, деск говорит сидеть
в стороне → ценность = избегнутый убыток. Книга накапливает forward-track по дням.

## Где / витрина / файлы
- Запуск: внутри worker-таска `calibrate` (оба — дешёвый детерминированный пересчёт из
  истории; без нового picker-бранча). Выход `data/desk/copytrade.json`.
- Витрина: плитка `/desk` (copy_all vs copy_desk: n, avg, win_rate, edge).
- `scripts/desk_copytrade.py` (+`_test.py`), вызов в `desk_worker.run_calibrate`,
  плитка + `loadDeskCopytrade` в `data.js`.

## Безопасность/честность
Paper-only, excess (рыночно-нейтральные) доходности, кап маленькой вселенной и короткой
истории выводим явно. Меряем эффект вётчинга, не торговая рекомендация.

## Тесты
- `book_stats(exs)` — n/avg/win_rate/total на известном списке.
- `build_signals(first, roster, snaps, copyok, horizon)` — синтетика: copy_desk ⊆ copy_all,
  правильная фильтрация по copy_ok.

## Вне scope
Сайзинг/TP/SL живого бота (B), conviction-веса (v2), кошельковая калибровка истории.
