"""The closed-form answers hold up when the test is actually simulated."""

import pytest

from readiness.simulate import simulated_power_proportion, simulated_variance_cut_cuped
from readiness.stats import cuped_factor, n_per_arm_proportion


def test_simulated_power_matches_target():
    n = n_per_arm_proportion(0.20, 0.25, power=0.80)
    assert simulated_power_proportion(0.20, 0.25, n, reps=4000, seed=1) == pytest.approx(0.80, abs=0.03)


def test_no_effect_rejects_about_alpha():
    n = n_per_arm_proportion(0.20, 0.25)
    rate = simulated_power_proportion(0.20, 0.0, n, reps=4000, seed=2)
    assert rate == pytest.approx(0.05, abs=0.015)


@pytest.mark.parametrize("rho", [0.3, 0.6, 0.9])
def test_cuped_variance_cut_matches_formula(rho):
    assert simulated_variance_cut_cuped(rho, seed=3) == pytest.approx(cuped_factor(rho), abs=0.02)
