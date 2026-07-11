import test from 'node:test';
import assert from 'node:assert/strict';
import { experimentEvidence, normalizeMindmapNode } from './mindmap.js';

test('mindmap node state fails closed and preserves known branches', () => {
  assert.equal(normalizeMindmapNode('experiment'), 'experiment');
  assert.equal(normalizeMindmapNode('unknown'), 'sources');
  assert.equal(normalizeMindmapNode(null, 'history'), 'history');
});

test('mindmap evidence status fails closed and exposes the IS-data block', () => {
  assert.equal(experimentEvidence(null).label, 'evidence: collecting');
  assert.equal(experimentEvidence({
    bundle_backtest: { candidate: true, confidence: { available: true, passed: false, in_sample: { n: 0 } } }
  }).label, 'evidence: collecting in-sample');
  assert.equal(experimentEvidence({
    bundle_backtest: { candidate: true, confidence: { available: true, passed: true } }
  }).tone, 'good');
});
