"""Sample-size and readiness maths for online experiments.

Everything here is closed-form and uses only the standard library, so it is easy to
check by hand. Conventions:

* ``alpha`` is two-sided.
* ``mde_rel`` is a relative lift: 0.10 means a 5.0% baseline must move to 5.5%.
* Sample sizes are per arm unless the name says otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

_N = NormalDist()


def z(p: float) -> float:
    """Standard normal quantile."""
    return _N.inv_cdf(p)


def _check_prob(name: str, value: float) -> None:
    if not 0.0 < value < 1.0:
        raise ValueError(f"{name} must be between 0 and 1, got {value}")


# --------------------------------------------------------------------------
# A/B test on a conversion rate
# --------------------------------------------------------------------------
def n_per_arm_proportion(
    baseline: float, mde_rel: float, alpha: float = 0.05, power: float = 0.80
) -> int:
    """Users per arm to detect a relative lift in a conversion rate.

    Two-sided z-test for two proportions, pooled variance under the null and
    unpooled under the alternative (the textbook Fleiss formula, no continuity
    correction).
    """
    _check_prob("baseline", baseline)
    _check_prob("alpha", alpha)
    _check_prob("power", power)
    p1 = baseline
    p2 = baseline * (1.0 + mde_rel)
    _check_prob("baseline * (1 + mde_rel)", p2)
    if p1 == p2:
        raise ValueError("mde_rel must not be zero")
    p_bar = (p1 + p2) / 2.0
    za, zb = z(1 - alpha / 2), z(power)
    num = za * math.sqrt(2 * p_bar * (1 - p_bar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return math.ceil(num**2 / (p2 - p1) ** 2)


def power_proportion(
    baseline: float, mde_rel: float, n_per_arm: int, alpha: float = 0.05
) -> float:
    """Power of the same test for a given sample size per arm."""
    p1 = baseline
    p2 = baseline * (1.0 + mde_rel)
    p_bar = (p1 + p2) / 2.0
    za = z(1 - alpha / 2)
    se0 = math.sqrt(2 * p_bar * (1 - p_bar) / n_per_arm)
    se1 = math.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n_per_arm)
    return _N.cdf((abs(p2 - p1) - za * se0) / se1)


def mde_proportion(
    baseline: float, n_per_arm: int, alpha: float = 0.05, power: float = 0.80
) -> float:
    """Smallest relative lift detectable with ``n_per_arm`` users per arm (bisection)."""
    lo, hi = 1e-6, (1.0 / baseline) - 1.0 - 1e-9
    if power_proportion(baseline, hi, n_per_arm, alpha) < power:
        return math.inf
    for _ in range(200):
        mid = (lo + hi) / 2
        if power_proportion(baseline, mid, n_per_arm, alpha) >= power:
            hi = mid
        else:
            lo = mid
    return hi


# --------------------------------------------------------------------------
# Continuous metric (e.g. revenue per user)
# --------------------------------------------------------------------------
def n_per_arm_mean(sd: float, delta: float, alpha: float = 0.05, power: float = 0.80) -> int:
    """Users per arm to detect an absolute difference ``delta`` in a mean."""
    if sd <= 0 or delta == 0:
        raise ValueError("sd must be positive and delta non-zero")
    za, zb = z(1 - alpha / 2), z(power)
    return math.ceil(2 * (za + zb) ** 2 * sd**2 / delta**2)


def mde_mean(sd: float, n_per_arm: int, alpha: float = 0.05, power: float = 0.80) -> float:
    """Smallest absolute difference in a mean detectable with ``n_per_arm`` users per arm."""
    if sd <= 0 or n_per_arm <= 0:
        raise ValueError("sd and n_per_arm must be positive")
    return (z(1 - alpha / 2) + z(power)) * sd * math.sqrt(2 / n_per_arm)


# --------------------------------------------------------------------------
# Variance reduction and clustering
# --------------------------------------------------------------------------
def cuped_factor(rho: float) -> float:
    """Share of the original sample needed after CUPED with pre-period correlation ``rho``.

    CUPED removes the part of the metric explained by its pre-experiment value, so
    variance (and therefore sample size) shrinks by ``1 - rho**2``.
    """
    if not -1.0 < rho < 1.0:
        raise ValueError("rho must be between -1 and 1")
    return 1.0 - rho**2


def design_effect(units_per_cluster: float, icc: float) -> float:
    """Variance inflation when outcomes inside a cluster (a time window) are correlated."""
    if units_per_cluster < 1:
        raise ValueError("units_per_cluster must be at least 1")
    if not 0.0 <= icc < 1.0:
        raise ValueError("icc must be in [0, 1)")
    return 1.0 + (units_per_cluster - 1.0) * icc


# --------------------------------------------------------------------------
# Switchback (randomise time windows within one market)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SwitchbackPlan:
    units_per_window: float
    design_effect: float
    windows_per_arm: int
    total_windows: int
    days: float


def switchback_plan(
    n_per_arm: int,
    daily_units: float,
    window_hours: float = 4.0,
    icc: float = 0.01,
    burn_in_share: float = 0.25,
) -> SwitchbackPlan:
    """Windows and days a switchback needs to match an A/B sample size.

    Each window is one randomised unit. Searches inside a window share the same
    market state, so they count for less than independent users (design effect).
    ``burn_in_share`` is the part of each window discarded to let carry-over from the
    previous arm wash out.
    """
    if not 0.0 <= burn_in_share < 1.0:
        raise ValueError("burn_in_share must be in [0, 1)")
    if daily_units <= 0 or window_hours <= 0:
        raise ValueError("daily_units and window_hours must be positive")
    windows_per_day = 24.0 / window_hours
    units = daily_units / windows_per_day * (1.0 - burn_in_share)
    units = max(units, 1.0)
    de = design_effect(units, icc)
    effective_per_window = units / de
    windows_per_arm = math.ceil(n_per_arm / effective_per_window)
    total = 2 * windows_per_arm
    return SwitchbackPlan(units, de, windows_per_arm, total, total / windows_per_day)


# --------------------------------------------------------------------------
# Interleaving (both rankers in one list, count which one wins each session)
# --------------------------------------------------------------------------
def n_sessions_interleaving(
    win_rate: float, alpha: float = 0.05, power: float = 0.80, tie_rate: float = 0.0
) -> int:
    """Sessions needed to show the new ranker wins more than half of decided sessions.

    One-sample test of a proportion against 0.5. ``tie_rate`` is the share of sessions
    with no click or a tie, which carry no information and are discarded.
    """
    _check_prob("win_rate", win_rate)
    if win_rate == 0.5:
        raise ValueError("win_rate must differ from 0.5")
    if not 0.0 <= tie_rate < 1.0:
        raise ValueError("tie_rate must be in [0, 1)")
    za, zb = z(1 - alpha / 2), z(power)
    num = za * 0.5 + zb * math.sqrt(win_rate * (1 - win_rate))
    decided = (num / (win_rate - 0.5)) ** 2
    return math.ceil(decided / (1.0 - tie_rate))


def days_needed(total_units: float, daily_units: float, traffic_share: float = 1.0) -> float:
    """Days to collect ``total_units`` when only ``traffic_share`` of traffic enters the test."""
    if daily_units <= 0 or not 0.0 < traffic_share <= 1.0:
        raise ValueError("daily_units must be positive and traffic_share in (0, 1]")
    return total_units / (daily_units * traffic_share)
