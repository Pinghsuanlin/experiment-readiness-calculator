"""Experiment readiness calculator: can this test reach a result, with which design, how fast."""

from .coverage import plan_table, summary
from .stats import (
    cuped_factor,
    days_needed,
    design_effect,
    mde_proportion,
    n_per_arm_mean,
    n_per_arm_proportion,
    n_sessions_interleaving,
    power_proportion,
    switchback_plan,
)

__all__ = [
    "cuped_factor",
    "days_needed",
    "design_effect",
    "mde_proportion",
    "n_per_arm_mean",
    "n_per_arm_proportion",
    "n_sessions_interleaving",
    "plan_table",
    "power_proportion",
    "summary",
    "switchback_plan",
]
__version__ = "0.1.0"
