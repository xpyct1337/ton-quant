// Visibility state for the Analytics page. Persists to localStorage.
// Layout/visibility are kept separate from the widget registry (widgets.js) on purpose.
import { READY_IDS, PRESETS } from './widgets.js';

const KEY = 'tq.analytics.visible';

function load() {
  if (typeof localStorage === 'undefined') return new Set(READY_IDS);
  try {
    const v = JSON.parse(localStorage.getItem(KEY));
    return Array.isArray(v) ? new Set(v) : new Set(READY_IDS);
  } catch {
    return new Set(READY_IDS);
  }
}

export const prefs = $state({ visible: load(), preset: 'Всё' });

function save() {
  try { localStorage.setItem(KEY, JSON.stringify([...prefs.visible])); } catch {}
}

// Reassign the Set (not mutate) so $derived consumers re-run.
export function toggle(id) {
  const s = new Set(prefs.visible);
  s.has(id) ? s.delete(id) : s.add(id);
  prefs.visible = s; prefs.preset = ''; save();
}
export function showAll() { prefs.visible = new Set(READY_IDS); prefs.preset = 'Всё'; save(); }
export function hideAll() { prefs.visible = new Set(); prefs.preset = ''; save(); }
export function applyPreset(name) { prefs.visible = new Set(PRESETS[name] || []); prefs.preset = name; save(); }
