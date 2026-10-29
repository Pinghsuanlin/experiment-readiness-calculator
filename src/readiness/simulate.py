"""Monte Carlo checks that the closed-form sample sizes deliver the power they promise."""

from __future__ import annotations

import numpy as np

from .stats import z


def simulated_power_proportion(
    baseline: float,
    mde_rel: float,
    n_per_arm: int,
    alpha: float = 0.05,
    reps: int = 4000,
    seed: int = 0,
) -> float:
    """Share of simulated A/B tests (true lift = ``mde_rel``) that reject the null."""
    rng = np.random.default_rng(seed)
    p1, p2 = baseline, baseline * (1 + mde_rel)
    x1 = rng.binomial(n_per_arm, p1, reps)
    x2 = rng.binomial(n_per_arm, p2, reps)
    pooled = (x1 + x2) / (2 * n_per_arm)
    se = np.sqrt(2 * pooled * (1 - pooled) / n_per_arm)
    stat = np.abs(x2 - x1) / n_per_arm / np.where(se > 0, se, np.inf)
    return float(np.mean(stat > z(1 - alpha / 2)))


def simulated_variance_cut_cuped(rho: float, n: int = 20000, seed: int = 0) -> float:
    """Observed share of variance left after CUPED on correlated synthetic data."""
    rng = np.random.default_rng(seed)
    pre = rng.normal(size=n)
    post = rho * pre + np.sqrt(1 - rho**2) * rng.normal(size=n)
    theta = np.cov(post, pre)[0, 1] / np.var(pre, ddof=1)
    adjusted = post - theta * (pre - pre.mean())
    return float(np.var(adjusted, ddof=1) / np.var(post, ddof=1))
