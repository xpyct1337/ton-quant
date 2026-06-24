// Widget registry — single source of truth for the Analytics page.
// Each entry: { id, title, group, ready, span, desc, component }.
// `ready:false` widgets are listed (greyed) but not yet renderable.
import Treemap from './components/Treemap.svelte';
import CorrMatrix from './components/CorrMatrix.svelte';
import Momentum from './components/Momentum.svelte';

export const GROUPS = ['Обзор', 'Моментум', 'Кросс-токен', 'Риск'];

export const WIDGETS = [
  { id: 'treemap', title: 'Market map', group: 'Обзор', ready: true, span: 2, component: Treemap,
    desc: 'Карта рынка: размер = mcap, цвет = доходность окна' },
  { id: 'corr', title: 'Correlation matrix', group: 'Кросс-токен', ready: true, span: 2, component: CorrMatrix,
    desc: 'Корреляции топ-12 + β к корзине' },
  { id: 'momentum', title: 'Momentum leaderboard', group: 'Моментум', ready: true, span: 1, component: Momentum,
    desc: 'RS-рейтинг 7/14/30d + тренд' },
  // backlog placeholders (порт/новое — next):
  { id: 'rsi', title: 'RSI + дивергенция', group: 'Моментум', ready: false, span: 1, desc: 'Wilder RSI(14) + дивергенция' },
  { id: 'leadlag', title: 'Lead–lag radar', group: 'Кросс-токен', ready: false, span: 1, desc: 'Кто двигается первым (лаг 1д)' },
  { id: 'riskret', title: 'Risk–return map', group: 'Риск', ready: false, span: 1, desc: 'Доходность vs волатильность' },
  { id: 'rugradar', title: 'Rug Radar', group: 'Риск', ready: false, span: 1, desc: 'TVL падает при стабильной цене' }
];

export const READY_IDS = WIDGETS.filter((w) => w.ready).map((w) => w.id);

// Presets = profiles. Only reference ready ids.
export const PRESETS = {
  'Всё': READY_IDS,
  'Трейдер': ['momentum', 'treemap'],
  'Инвестор': ['corr', 'treemap']
};
