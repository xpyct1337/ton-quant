export const featuredWallets = [
  {
    address: 'EQDYzZmfsrGzhObKJUw4gzdeIxEai3jAFbiGKGwxvxHinaPP',
    label: 'Pavel Durov · wallet 1'
  },
  {
    address: 'EQCjVdfH3kW7aEWl3VJXmMyiPNUYymAbnGqTJJOugikreUkI',
    label: 'Pavel Durov · wallet 2'
  }
];

export function walletSlug(address) {
  return /^0:[0-9a-f]+$/i.test(address) ? `raw-${address.slice(2)}` : encodeURIComponent(address);
}

export function walletAddress(slug) {
  return slug.startsWith('raw-') ? `0:${slug.slice(4)}` : decodeURIComponent(slug);
}

export function walletHref(base, address) {
  return `${base}/wallet/${walletSlug(address)}/`;
}
