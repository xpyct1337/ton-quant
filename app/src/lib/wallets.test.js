import test from 'node:test';
import assert from 'node:assert/strict';
import { featuredWallets, walletAddress, walletHref, walletSlug } from './wallets.js';

test('wallet routes preserve user-friendly and raw TON addresses', () => {
  const friendly = featuredWallets[0].address;
  assert.equal(walletAddress(walletSlug(friendly)), friendly);
  const raw = '0:' + 'a'.repeat(64);
  assert.equal(walletAddress(walletSlug(raw)), raw);
  assert.match(walletHref('/ton-quant', friendly), /\/wallet\/EQ/);
});
