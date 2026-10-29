"""Known answers for the closed-form maths."""

import math

import pytest

from readiness.stats import (
    cuped_factor,
    days_needed,
    design_effect,
    mde_proportion,
    n_per_arm_mean,
    mde_mean,
    n_per_arm_proportion,
    n_sessions_interleaving,
    power_proportion,
    switchback_plan,
)


def test_proportion_matches_textbook_values():
    # Fleiss formula, no continuity correction: 10% -> 12% needs 3,841 per arm.
    assert n_per_arm_proportion(0.10, 0.20) == 3841
    # 5% baseline, 10% relative lift: 31,234 per arm.
    assert n_per_arm_proportion(0.05, 0.10) == 31234


def test_power_at_computed_n_is_target():
    n = n_per_arm_proportion(0.05, 0.10, power=0.80)
    assert power_proportion(0.05, 0.10, n) == pytest.approx(0.80, abs=0.002)


def test_mde_inverts_sample_size():
    n = n_per_arm_proportion(0.05, 0.10)
    assert mde_proportion(0.05, n) == pytest.approx(0.10, abs=1e-3)


def test_smaller_effects_need_more_users():
    assert n_per_arm_proportion(0.05, 0.05) > n_per_arm_proportion(0.05, 0.10) * 3.5


def test_mean_matches_rule_of_thumb():
    # 2 * (1.96 + 0.84)^2 / d^2 for d = 0.1 sd: 1,570 per arm.
    assert n_per_arm_mean(1.0, 0.1) == 1570


def test_cuped_and_design_effect():
    assert cuped_factor(0.6) == pytest.approx(0.64)
    assert design_effect(1, 0.3) == 1.0
    assert design_effect(101, 0.01) == pytest.approx(2.0)


def test_interleaving_hand_calculation():
    expected = math.ceil(((1.959964 * 0.5 + 0.841621 * math.sqrt(0.55 * 0.45)) / 0.05) ** 2)
    assert n_sessions_interleaving(0.55) == expected
    # Half the sessions undecided doubles the sessions needed.
    assert n_sessions_interleaving(0.55, tie_rate=0.5) == pytest.approx(2 * expected, abs=1)


def test_switchback_needs_more_traffic_than_ab():
    n = n_per_arm_proportion(0.05, 0.10)
    ab_days = days_needed(2 * n, 20000)
    sb = switchback_plan(n, 20000, window_hours=4, icc=0.01, burn_in_share=0.25)
    assert sb.days > ab_days
    assert sb.total_windows == 2 * sb.windows_per_arm


def test_switchback_with_no_correlation_and_no_burn_in_matches_ab():
    n = 10000
    sb = switchback_plan(n, 12000, window_hours=4, icc=0.0, burn_in_share=0.0)
    assert sb.days == pytest.approx(days_needed(2 * n, 12000), rel=0.01)


@pytest.mark.parametrize(
    "call",
    [
        lambda: n_per_arm_proportion(0.0, 0.1),
        lambda: n_per_arm_proportion(0.5, 0.0),
        lambda: n_per_arm_proportion(0.6, 1.0),
        lambda: n_sessions_interleaving(0.5),
        lambda: cuped_factor(1.0),
        lambda: switchback_plan(100, 1000, burn_in_share=1.0),
        lambda: days_needed(10, 0),
    ],
)
def test_bad_inputs_raise(call):
    with pytest.raises(ValueError):
        call()


def test_mde_mean_inverts_sample_size():
    n = n_per_arm_mean(80.0, 1.0)
    assert 0.99 < mde_mean(80.0, n) <= 1.0


def test_doubling_sd_quadruples_users():
    base = n_per_arm_mean(40.0, 2.0)
    assert abs(n_per_arm_mean(80.0, 2.0) / base - 4) < 0.01
