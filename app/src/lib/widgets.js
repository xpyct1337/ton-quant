// Widget registry — single source of truth for the Analytics page.
// Each entry: { id, title, group, ready, span, desc, component }.
// `ready:false` widgets are listed (greyed) but not yet renderable.
import Treemap from './components/Treemap.svelte';
import CorrMatrix from './components/CorrMatrix.svelte';
import Momentum from './components/Momentum.svelte';
import Rsi from './components/Rsi.svelte';
import Macd from './components/Macd.svelte';
import Reversal from './components/Reversal.svelte';
import LeadLag from './components/LeadLag.svelte';
import RiskReturn from './components/RiskReturn.svelte';
import Drawdown from './components/Drawdown.svelte';
import WashDetector from './components/WashDetector.svelte';
import PHRatio from './components/PHRatio.svelte';
import Absorption from './components/Absorption.svelte';
import RugRadar from './components/RugRadar.svelte';

export const GROUPS = ['Обзор', 'Моментум', 'Кросс-токен', 'Риск', 'Микроструктура'];

export const WIDGETS = [
  { id: 'treemap', title: 'Market map', group: 'Обзор', ready: true, span: 2, component: Treemap,
    desc: 'Карта рынка: размер = mcap, цвет = доходность окна' },

  { id: 'momentum', title: 'Momentum leaderboard', group: 'Моментум', ready: true, span: 1, component: Momentum,
    desc: 'RS-рейтинг 7/14/30d + тренд' },
  { id: 'rsi', title: 'RSI + дивергенция', group: 'Моментум', ready: true, span: 1, component: Rsi,
    desc: 'Wilder RSI(14) + дивергенция (нужно ≥15 дней)' },
  { id: 'macd', title: 'MACD trend', group: 'Моментум', ready: true, span: 1, component: Macd,
    desc: 'MACD(12,26,9) + кроссовер + дивергенция (нужно ≥35 дней)' },
  { id: 'reversal', title: 'Reversal watch', group: 'Моментум', ready: true, span: 1, component: Reversal,
    desc: 'Синтез RSI+MACD дивергенций (двойное подтверждение)' },

  { id: 'corr', title: 'Correlation matrix', group: 'Кросс-токен', ready: true, span: 2, component: CorrMatrix,
    desc: 'Корреляции топ-12 + β к корзине' },
  { id: 'leadlag', title: 'Lead–lag radar', group: 'Кросс-токен', ready: true, span: 1, component: LeadLag,
    desc: 'Кто двигается первым (лаг 1д)' },
  { id: 'phratio', title: 'P/H ratio', group: 'Кросс-токен', ready: true, span: 1, component: PHRatio,
    desc: 'Mcap на холдера vs медиана — скрининг переоценки' },

  { id: 'riskret', title: 'Risk–return map', group: 'Риск', ready: true, span: 2, component: RiskReturn,
    desc: 'Доходность vs волатильность, Sharpe' },
  { id: 'drawdown', title: 'Drawdown radar', group: 'Риск', ready: true, span: 1, component: Drawdown,
    desc: 'Просадка от 40д-хая + позиция в диапазоне' },

  { id: 'wash', title: 'Wash detector', group: 'Микроструктура', ready: true, span: 1, component: WashDetector,
    desc: 'Турновер vol/TVL — флаг накрутки объёма' },
  { id: 'absorption', title: 'Volume × Price', group: 'Микроструктура', ready: true, span: 1, component: Absorption,
    desc: 'Абсорбция: поток сделок против цены' },

  { id: 'rugradar', title: 'Rug Radar', group: 'Риск', ready: true, span: 1, component: RugRadar,
    desc: 'Отток ликвидности: TVL падает при держащейся цене (0 запросов)' }
];

export const READY_IDS = WIDGETS.filter((w) => w.ready).map((w) => w.id);

// Presets = profiles. Only reference ready ids.
export const PRESETS = {
  'Всё': READY_IDS,
  'Трейдер': ['momentum', 'rsi', 'macd', 'reversal', 'absorption', 'treemap'],
  'Инвестор': ['corr', 'riskret', 'drawdown', 'phratio', 'treemap'],
  'Риск-менеджер': ['riskret', 'drawdown', 'rugradar', 'reversal', 'wash', 'corr']
};
