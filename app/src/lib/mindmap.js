export const MINDMAP_NODE_IDS = new Set([
  'sources', 'hypothesis', 'experiment', 'validation',
  'desk', 'showcase', 'log', 'data', 'ledger', 'history'
]);

export function normalizeMindmapNode(value, fallback = 'sources') {
  return MINDMAP_NODE_IDS.has(value) ? value : fallback;
}

export function experimentEvidence(calibration) {
  const bundle = calibration?.bundle_backtest;
  const confidence = bundle?.confidence;
  if (!bundle || !confidence) return { tone: 'muted', label: 'evidence: collecting' };
  if (confidence.passed) return { tone: 'good', label: 'evidence: confidence gate passed' };
  if (bundle.candidate && confidence.available) {
    return confidence.in_sample?.n ?
      { tone: 'warn', label: 'evidence: gate not passed' } :
      { tone: 'warn', label: 'evidence: collecting in-sample' };
  }
  return { tone: 'muted', label: 'evidence: collecting' };
}

export function mindmapNextAction(calibration) {
  const bundle = calibration?.bundle_backtest;
  const confidence = bundle?.confidence;
  if (!bundle) return { id: 'sources', label: 'собрать evidence' };
  if (bundle.candidate && confidence?.available && !confidence.passed && !confidence.in_sample?.n) {
    return { id: 'data', label: 'собрать IS-историю' };
  }
  if (bundle.candidate && confidence?.available && !confidence.passed) {
    return { id: 'validation', label: 'разобрать confidence gate' };
  }
  return { id: confidence?.passed ? 'validation' : 'data', label: confidence?.passed ? 'подтвердить OOS' : 'дождаться coverage' };
}
