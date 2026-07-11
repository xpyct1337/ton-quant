import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeMindmapNode } from './mindmap.js';

test('mindmap node state fails closed and preserves known branches', () => {
  assert.equal(normalizeMindmapNode('experiment'), 'experiment');
  assert.equal(normalizeMindmapNode('unknown'), 'sources');
  assert.equal(normalizeMindmapNode(null, 'history'), 'history');
});
