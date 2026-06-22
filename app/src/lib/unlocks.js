// Supply-pressure heuristics. ponytail: client-side derivable only — staking unstake
// windows + emission category; precise team cliffs need an external schedule source (n/a).
const STAKE_WINDOW = { staking: 'unstake ~36h', stable: 'mint/redeem открытый' };

export function buildUnlocks(rows) {
  return rows
    .map((r) => {
      let event = null, pressure = 0;
      if (STAKE_WINDOW[r.cat]) { event = STAKE_WINDOW[r.cat]; pressure = Math.min(r.volTvl * 20, 60); }
      else if (r.growth && r.growth.pct > 3) { event = 'эмиссия/приток холдеров'; pressure = Math.min(r.growth.pct, 50); }
      if (!event) return null;
      return { sym: r.sym, addr: r.addr, event, pct: Math.round(pressure),
        usd: r.tvl * (pressure / 100) };
    })
    .filter(Boolean)
    .sort((a, b) => b.pct - a.pct)
    .slice(0, 6);
}
