"""Readiness table: which market cells can run a test, with which design, and how fast.

Input: one row per cell (for example city x category) with its daily traffic and
baseline conversion rate. Output: the same rows with the chosen design, days to a
result and a red / amber / green status.
"""

from __future__ import annotations

import pandas as pd

from .stats import cuped_factor, days_needed, n_per_arm_proportion, switchback_plan

REQUIRED = ("cell", "daily_units", "baseline_rate")


def plan_table(
    cells: pd.DataFrame,
    mde_rel: float = 0.10,
    alpha: float = 0.05,
    power: float = 0.80,
    traffic_share: float = 1.0,
    cuped_rho: float = 0.0,
    window_hours: float = 4.0,
    icc: float = 0.01,
    burn_in_share: float = 0.25,
    green_days: float = 14.0,
    amber_days: float = 42.0,
) -> pd.DataFrame:
    """Add design, sample size, days and status to each cell.

    A cell marked ``supply_constrained`` (sellers run out of capacity, so arms would
    compete for the same supply) gets a switchback; any other cell gets a plain
    within-cell A/B, which is cheaper.
    """
    missing = [c for c in REQUIRED if c not in cells.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")
    if green_days > amber_days:
        raise ValueError("green_days must not exceed amber_days")

    out = cells.copy()
    if "supply_constrained" not in out.columns:
        out["supply_constrained"] = False
    out["supply_constrained"] = out["supply_constrained"].astype(bool)
    factor = cuped_factor(cuped_rho)

    designs, n_arm, days = [], [], []
    for row in out.itertuples(index=False):
        n = n_per_arm_proportion(row.baseline_rate, mde_rel, alpha, power)
        n = max(1, round(n * factor))
        if row.supply_constrained:
            plan = switchback_plan(n, row.daily_units * traffic_share, window_hours, icc, burn_in_share)
            designs.append("switchback")
            days.append(plan.days)
        else:
            designs.append("A/B")
            days.append(days_needed(2 * n, row.daily_units, traffic_share))
        n_arm.append(n)

    out["design"] = designs
    out["n_per_arm"] = n_arm
    out["days_to_result"] = [round(x, 1) for x in days]
    out["status"] = [
        "green" if d <= green_days else "amber" if d <= amber_days else "red" for d in days
    ]
    return out.sort_values("days_to_result").reset_index(drop=True)


def summary(table: pd.DataFrame) -> dict[str, int]:
    """Count of cells per status."""
    counts = table["status"].value_counts()
    return {s: int(counts.get(s, 0)) for s in ("green", "amber", "red")}
