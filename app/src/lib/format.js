export const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export const shortAddr = (a) => (a ? a.slice(0, 4) + '…' + a.slice(-4) : '');

export function fmtUsd(v) {
  if (v == null || !isFinite(v)) return '—';
  const a = Math.abs(v);
  if (a >= 1e9) return '$' + (v / 1e9).toFixed(2) + 'B';
  if (a >= 1e6) return '$' + (v / 1e6).toFixed(2) + 'M';
  if (a >= 1e3) return '$' + (v / 1e3).toFixed(1) + 'K';
  if (a >= 1) return '$' + v.toFixed(2);
  if (a === 0) return '$0';
  return '$' + v.toPrecision(2);
}

export const fmtPct = (v, d = 1) =>
  v == null || !isFinite(v) ? '—' : (v >= 0 ? '+' : '') + v.toFixed(d) + '%';

export const fmtNum = (v) => (v == null || !isFinite(v) ? '—' : Math.round(v).toLocaleString('en-US'));
