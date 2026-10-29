"""Readiness table behaviour on small hand-built inputs."""

from pathlib import Path

import pandas as pd
import pytest

from readiness.coverage import plan_table, summary

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_cells.csv"


def cells():
    return pd.DataFrame(
        {
            "cell": ["big", "small", "busy"],
            "daily_units": [50000, 300, 50000],
            "baseline_rate": [0.05, 0.05, 0.05],
            "supply_constrained": [False, False, True],
        }
    )


def test_designs_and_ordering():
    t = plan_table(cells())
    assert list(t["cell"]) == sorted(t["cell"], key=lambda c: t.set_index("cell").loc[c, "days_to_result"])
    by = t.set_index("cell")
    assert by.loc["busy", "design"] == "switchback"
    assert by.loc["big", "design"] == "A/B"
    assert by.loc["big", "status"] == "green"
    assert by.loc["small", "status"] == "red"
    assert by.loc["busy", "days_to_result"] > by.loc["big", "days_to_result"]


def test_cuped_shortens_every_cell():
    plain = plan_table(cells()).set_index("cell")["days_to_result"]
    cuped = plan_table(cells(), cuped_rho=0.5).set_index("cell")["days_to_result"]
    assert (cuped <= plain).all() and (cuped < plain).any()


def test_summary_counts_all_cells():
    t = plan_table(cells())
    assert sum(summary(t).values()) == len(t)


def test_missing_column_raises():
    with pytest.raises(ValueError):
        plan_table(cells().drop(columns=["baseline_rate"]))


def test_sample_file_runs():
    t = plan_table(pd.read_csv(SAMPLE))
    assert len(t) == len(pd.read_csv(SAMPLE))
    assert set(t["status"]) <= {"green", "amber", "red"}
