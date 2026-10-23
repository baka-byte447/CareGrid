"""Guards the load calibration of the default dataset and the surge scenarios.

If someone regenerates data/synthetic/patients.csv with unrealistic arrival
rates (the original 5/hour asked a 100-bed hospital to absorb ~5x its capacity),
these tests fail loudly instead of silently making every later RL-vs-baseline
comparison meaningless."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from experiments.run_experiment import run_experiment
from simulator.hospital.scenarios import SCENARIO_MULTIPLIERS, scale_arrivals
from simulator.patients.patient import Patient

DATA_DIR = str(Path(__file__).resolve().parents[2] / "data" / "synthetic")
T0 = datetime(2026, 1, 1, 8, 0, 0)


def _p(pid, minutes):
    return Patient(pid, "45-64", 3, "General", 2.0, False, False, T0 + timedelta(minutes=minutes))


# ---------- scale_arrivals ----------

def test_scale_arrivals_compresses_from_the_earliest_arrival():
    pts = [_p("A", 0), _p("B", 60), _p("C", 120)]
    scale_arrivals(pts, 2.0)
    assert [p.arrival_time for p in pts] == [T0, T0 + timedelta(minutes=30), T0 + timedelta(minutes=60)]


def test_scale_arrivals_identity_and_validation():
    pts = [_p("A", 0), _p("B", 60)]
    scale_arrivals(pts, 1.0)
    assert pts[1].arrival_time == T0 + timedelta(minutes=60)
    scale_arrivals([], 3.0)                      # empty list is fine
    with pytest.raises(ValueError):
        scale_arrivals(pts, 0)


# ---------- calibration of the committed dataset ----------

@pytest.fixture(scope="module")
def ladder():
    return {name: run_experiment("rule_based", name, DATA_DIR, "patients.csv")["metrics"]
            for name in SCENARIO_MULTIPLIERS}


def test_normal_scenario_is_a_healthy_busy_hospital(ladder):
    m = ladder["normal"]
    assert m["patients_still_waiting"] == 0
    assert m["median_wait_min"] == 0                       # most patients get a bed on arrival
    assert 0.45 <= m["overall_bed_utilization"] <= 0.80    # busy, but not overloaded
    assert m["pct_admitted_within_60min"] >= 0.70
    assert m["avg_wait_min"] < 24 * 60                     # average wait well under a day
    assert m["constraint_violations"]["total"] == 0


def test_surge_scenarios_escalate(ladder):
    n, mod, sev = (ladder[k] for k in ("normal", "moderate_surge", "severe_surge"))
    assert n["avg_wait_min"] < mod["avg_wait_min"] < sev["avg_wait_min"]
    assert sev["avg_wait_min"] > 3 * n["avg_wait_min"]
    assert n["overall_bed_utilization"] < mod["overall_bed_utilization"]
    assert mod["constraint_violations"]["total"] == sev["constraint_violations"]["total"] == 0
