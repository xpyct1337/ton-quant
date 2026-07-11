import test from 'node:test';
import assert from 'node:assert/strict';
import { experimentEvidence, mindmapNextAction, normalizeMindmapNode } from './mindmap.js';

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
  assert.equal(experimentEvidence({
    bundle_backtest: { confidence: { available: false, reason: 'insufficient_matured_dates' } }
  }).label, 'evidence: waiting for mature window');
  assert.equal(experimentEvidence({
    bundle_backtest: { confidence: { available: false, reason: 'insufficient_matured_dates' } },
    momentum_test: { available: true, passed: false }
  }).label, 'evidence: waiting for mature window · mom_7d rejected');
});

test('mindmap next action points to data while IS history is empty', () => {
  assert.equal(mindmapNextAction(null).id, 'sources');
  assert.deepEqual(mindmapNextAction({
    bundle_backtest: { candidate: true, confidence: { available: true, passed: false, in_sample: { n: 0 } } }
  }), { id: 'data', label: 'собрать IS-историю' });
  assert.deepEqual(mindmapNextAction({
    bundle_backtest: { confidence: { available: false, reason: 'insufficient_matured_dates' } }
  }), { id: 'data', label: 'дождаться зрелой IS-истории' });
  assert.equal(mindmapNextAction({
    bundle_backtest: { candidate: true, confidence: { available: true, passed: true } }
  }).id, 'validation');
});
