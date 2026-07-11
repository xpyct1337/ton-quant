import test from 'node:test';
import assert from 'node:assert/strict';
import { NODES, EDGES, nodeStatus, layout } from './health-graph.js';

test('nodeStatus classifies against updated_at, not baked status', () => {
  const now = Date.parse('2026-07-11T12:00:00Z');
  assert.equal(nodeStatus(null, now), 'unknown');
  assert.equal(nodeStatus({ status: 'error' }, now), 'error');
  assert.equal(nodeStatus({ status: 'missing' }, now), 'missing');
  // fresh: 1h old, threshold 6h
  assert.equal(nodeStatus({ status: 'ok', updated_at: '2026-07-11T11:00:00Z', max_age_h: 6 }, now), 'ok');
  // stale: 8h old, threshold 6h — recomputed even though baked status said ok
  assert.equal(nodeStatus({ status: 'ok', updated_at: '2026-07-11T04:00:00Z', max_age_h: 6 }, now), 'stale');
});

test('layout places every node and only real edges, with desk deepest', () => {
  const keys = Object.keys(NODES);
  const { nodes, links } = layout(keys, EDGES, 1000, 400);
  assert.equal(nodes.length, keys.length);
  assert.ok(nodes.every((n) => n && Number.isFinite(n.x) && Number.isFinite(n.y)));
  assert.equal(links.length, EDGES.length);
  // desk depends on wallets+signals+flows+forensics(<-snapshot), so it sits right
  // of snapshot — larger x — confirming the layered depth ordering.
  const x = Object.fromEntries(nodes.map((n) => [n.key, n.x]));
  assert.ok(x.desk > x.snapshot);
  assert.ok(x.xs_audit > x.xs_forward);
});
