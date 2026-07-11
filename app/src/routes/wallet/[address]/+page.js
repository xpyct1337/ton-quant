import { featuredWallets, walletSlug } from '$lib/wallets.js';
import rosterData from '../../../../../data/wallets.json';

export const prerender = true;
export const entries = () => [
  ...featuredWallets.map(({ address }) => ({ address })),
  ...(rosterData.roster || []).map(({ addr }) => ({ address: walletSlug(addr) }))
];
