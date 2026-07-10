"""Small, dependency-free diagnostics for XS momentum research and paper tracking.

These functions deliberately do not decide whether a strategy is tradable.  They
make the limits of the available evidence machine-readable instead.
"""
from bisect import bisect_left
from itertools import combinations
from math import erf, sqrt
from statistics import median


def _mean(values):
    return sum(values) / len(values) if values else None


def _rank_percentile(value, values):
    """Mid-rank percentile: 0 is worst, 1 is best."""
    below = sum(other < value for other in values)
    equal = sum(other == value for other in values)
    return (below + equal / 2) / len(values)


def cscv_pbo(config_returns, groups=8, embargo_ms=0):
    """Combinatorially symmetric CV PBO with a time embargo.

    ``config_returns`` maps a configuration name to ``{timestamp: return}``.
    Every split selects a configuration on purged training observations and ranks
    that same configuration against all candidates on the held-out observations.
    PBO is the share of selected configurations ranked in the lower half OOS.
    """
    series = {name: dict(values) for name, values in config_returns.items()}
    if len(series) < 2:
        raise ValueError("need at least two configurations")
    timestamps = sorted(set.intersection(*(set(row) for row in series.values())))
    if len(timestamps) < groups or groups < 2 or groups % 2:
        raise ValueError("need an even group count no larger than common observations")

    folds = [timestamps[i::groups] for i in range(groups)]
    ranks, oos_means, train_sizes = [], [], []
    for train_folds in combinations(range(groups), groups // 2):
        test = sorted(ts for fold in range(groups) if fold not in train_folds for ts in folds[fold])
        raw_train = [ts for fold in train_folds for ts in folds[fold]]
        train = _purged(raw_train, test, embargo_ms)
        if not train or not test:
            continue
        train_means = {name: _mean([row[ts] for ts in train]) for name, row in series.items()}
        selected = max(train_means, key=train_means.get)
        test_means = {name: _mean([row[ts] for ts in test]) for name, row in series.items()}
        rank = _rank_percentile(test_means[selected], list(test_means.values()))
        ranks.append(rank)
        oos_means.append(test_means[selected])
        train_sizes.append(len(train))

    if not ranks:
        raise ValueError("no valid CSCV splits")
    return {
        "observations": len(timestamps),
        "groups": groups,
        "splits": len(ranks),
        "embargo_ms": embargo_ms,
        "median_train_observations": median(train_sizes),
        "pbo": sum(rank <= 0.5 for rank in ranks) / len(ranks),
        "median_test_rank": median(ranks),
        "median_selected_test_mean": median(oos_means),
        "selected_positive_share": sum(value > 0 for value in oos_means) / len(oos_means),
    }


def _purged(train, test, embargo_ms):
    if embargo_ms <= 0:
        return train
    test = sorted(test)
    kept = []
    for ts in train:
        index = bisect_left(test, ts)
        nearest = []
        if index:
            nearest.append(test[index - 1])
        if index < len(test):
            nearest.append(test[index])
        if not nearest or min(abs(ts - other) for other in nearest) > embargo_ms:
            kept.append(ts)
    return kept


def sharpe_diagnostic(returns, trial_count=1):
    """PSR-like descriptive probability with a transparent trial adjustment.

    This is deliberately a diagnostic, not a deployment gate: it cannot recover
    parameters tried before this script or correct the survivor-only universe.
    """
    values = list(returns)
    if len(values) < 3:
        return {"holds": len(values), "available": False}
    avg = _mean(values)
    variance = _mean([(value - avg) ** 2 for value in values])
    if variance == 0:
        return {"holds": len(values), "available": False}
    sd = sqrt(variance)
    sharpe = avg / sd
    z = sharpe * sqrt(len(values) - 1)
    psr_zero = 0.5 * (1 + erf(z / sqrt(2)))
    # Bonferroni is intentionally conservative and transparent for this small grid.
    adjusted_probability = max(0.0, 1 - min(1, trial_count) * (1 - psr_zero))
    return {
        "holds": len(values),
        "available": True,
        "unannualized_sharpe": sharpe,
        "psr_zero": psr_zero,
        "trial_count": trial_count,
        "bonferroni_adjusted_probability": adjusted_probability,
    }


def basket_outcome(open_pos, prices, fee):
    """Score a complete paper basket; never silently drop an unavailable symbol."""
    entry = open_pos.get("entry", {})
    long, short = open_pos.get("long", []), open_pos.get("short", [])

    def missing(names):
        return [name for name in names if not isinstance(entry.get(name), (int, float))
                or entry.get(name, 0) <= 0 or not isinstance(prices.get(name), (int, float))
                or prices.get(name, 0) <= 0]

    missing_long, missing_short = missing(long), missing(short)
    if not long or not short or missing_long or missing_short:
        return {"complete": False, "missing_long": missing_long, "missing_short": missing_short}
    long_gross = _mean([prices[name] / entry[name] - 1 for name in long])
    short_gross = _mean([prices[name] / entry[name] - 1 for name in short])
    fees = 2 * fee
    return {
        "complete": True,
        "long_gross": long_gross,
        "short_gross": short_gross,
        "fees": fees,
        "net": long_gross - short_gross - fees,
        "missing_long": [],
        "missing_short": [],
    }
