export const MINDMAP_NODE_IDS = new Set([
  'sources', 'hypothesis', 'experiment', 'validation',
  'desk', 'showcase', 'log', 'data', 'ledger', 'history'
]);

export function normalizeMindmapNode(value, fallback = 'sources') {
  return MINDMAP_NODE_IDS.has(value) ? value : fallback;
}
