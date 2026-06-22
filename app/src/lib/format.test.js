import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fmtUsd, fmtPct, esc, shortAddr } from './format.js';
import { tmColor } from './metrics.js';

test('fmtUsd scales K/M/B', () => {
  assert.equal(fmtUsd(1234), '$1.2K');
  assert.equal(fmtUsd(2.5e6), '$2.50M');
  assert.equal(fmtUsd(1.5e9), '$1.50B');
  assert.equal(fmtUsd(0), '$0');
  assert.equal(fmtUsd(null), '—');
});

test('fmtPct signs and guards', () => {
  assert.equal(fmtPct(5), '+5.0%');
  assert.equal(fmtPct(-3.2), '-3.2%');
  assert.equal(fmtPct(null), '—');
});

test('esc neutralizes html', () => {
  assert.ok(!/[<>"]/.test(esc('<img src=x onerror="a">')));
});

test('shortAddr trims', () => {
  assert.equal(shortAddr('EQDuGgqZ...f8GhzMf'.padEnd(48, 'x')).includes('…'), true);
});

test('tmColor: neutral gray, finite rgb for moves', () => {
  assert.equal(tmColor(0.05), '#7c8497');
  assert.equal(tmColor(NaN), '#7c8497');
  assert.ok(tmColor(8).startsWith('rgb('));
  assert.ok(tmColor(-8).startsWith('rgb('));
});
