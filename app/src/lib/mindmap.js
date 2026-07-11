export const MINDMAP_NODE_IDS = new Set([
  'sources', 'hypothesis', 'experiment', 'validation',
  'desk', 'showcase', 'log', 'data', 'ledger', 'history'
]);

export function normalizeMindmapNode(value, fallback = 'sources') {
  return MINDMAP_NODE_IDS.has(value) ? value : fallback;
}

export function mindmapPrompt(title, description, evidence, nextAction) {
  return `Продолжить TON Quant по ветке «${title}». ${description}\n\nТекущий evidence: ${evidence.label}. Следующий шаг: ${nextAction.label}.\n\nВыбери следующий фальсифицируемый минимальный шаг по Ponytail, реализуй и проверь его. Обновляй docs/PROJECT-MAP.md и ROADMAP-v3.md только если меняется решение.`;
}

function withMomentumStatus(label, calibration) {
  const test = calibration?.momentum_test;
  return test?.available ? `${label} · mom_7d ${test.passed ? 'passed' : 'rejected'}` : label;
}

export function experimentEvidence(calibration) {
  const bundle = calibration?.bundle_backtest;
  const confidence = bundle?.confidence;
  if (!bundle || !confidence) return { tone: 'muted', label: withMomentumStatus('evidence: collecting', calibration) };
  if (confidence.reason === 'insufficient_matured_dates') {
    const coverage = confidence.matured_dates && confidence.required_dates ? ` (${confidence.matured_dates}/${confidence.required_dates})` : '';
    return { tone: 'warn', label: withMomentumStatus(`evidence: waiting for mature window${coverage}`, calibration) };
  }
  if (confidence.passed) return { tone: 'good', label: withMomentumStatus('evidence: confidence gate passed', calibration) };
  if (bundle.candidate && confidence.available) {
    return confidence.in_sample?.n ?
      { tone: 'warn', label: withMomentumStatus('evidence: gate not passed', calibration) } :
      { tone: 'warn', label: withMomentumStatus('evidence: collecting in-sample', calibration) };
  }
  return { tone: 'muted', label: withMomentumStatus('evidence: collecting', calibration) };
}

export function mindmapNextAction(calibration) {
  const bundle = calibration?.bundle_backtest;
  const confidence = bundle?.confidence;
  if (!bundle) return { id: 'sources', label: 'собрать evidence' };
  if (confidence?.reason === 'insufficient_matured_dates') {
    return { id: 'data', label: 'дождаться зрелой IS-истории' };
  }
  if (bundle.candidate && confidence?.available && !confidence.passed && !confidence.in_sample?.n) {
    return { id: 'data', label: 'собрать IS-историю' };
  }
  if (bundle.candidate && confidence?.available && !confidence.passed) {
    return { id: 'validation', label: 'разобрать confidence gate' };
  }
  return { id: confidence?.passed ? 'validation' : 'data', label: confidence?.passed ? 'подтвердить OOS' : 'дождаться coverage' };
}
