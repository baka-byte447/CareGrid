"""Tests for the Phase 5 metrics pipeline, using tiny hand-built hospitals
so every expected number can be checked by hand."""
from datetime import datetime, timedelta

from simulator.hospital.engine import SimulationEngine, BED_CLEANING_MINUTES
from simulator.hospital.state import Bed, Equipment, HospitalState
from simulator.metrics.audit import audit_violations
from simulator.metrics.collector import MetricsCollector
from simulator.metrics.summary import compute_metrics
from simulator.patients.patient import Patient

T0 = datetime(2026, 1, 1, 8, 0, 0)


def make_state(beds, vents=0):
    s = HospitalState()
    for bid, btype, iso in beds:
        s.beds[bid] = Bed(bid, btype, "W", "AVAILABLE", iso)
    for i in range(vents):
        s.equipment[f"V{i}"] = Equipment(f"V{i}", "VENTILATOR", "AVAILABLE", "ICU")
    return s


def make_patient(pid, acuity, los_days, arrival, iso=False, vent=False):
    return Patient(pid, "45-64", acuity, "General", los_days, iso, vent, arrival)


def run(state, patients, window_end):
    eng = SimulationEngine(state, patients)
    eng.seed_arrivals()
    col = MetricsCollector(T0, window_end)
    eng.run(on_tick=col.on_tick)
    return eng, col


def test_utilization_is_time_weighted():
    # 1 ICU bed occupied for exactly 1 day inside a 2-day window -> 50%
    eng, col = run(make_state([("ICU-1", "ICU", True)]),
                   [make_patient("P1", 5, 1.0, T0)], T0 + timedelta(days=2))
    m = compute_metrics(eng, col)
    assert m["icu_utilization"] == 0.5
    assert m["constraint_violations"]["total"] == 0


def test_waiting_time_when_bed_is_busy():
    # one ICU bed, two critical patients arriving together:
    # the second waits LOS + cleaning time
    state = make_state([("ICU-1", "ICU", True)])
    pts = [make_patient("P1", 5, 1.0, T0), make_patient("P2", 5, 1.0, T0)]
    eng, col = run(state, pts, T0 + timedelta(days=5))
    m = compute_metrics(eng, col)
    expected = 1440 + BED_CLEANING_MINUTES
    assert m["max_wait_min"] == expected
    assert m["avg_wait_min"] == expected / 2
    assert m["peak_waiting_queue"] == 1
    assert m["patients_still_waiting"] == 0


def test_ventilator_utilization():
    eng, col = run(make_state([("ICU-1", "ICU", True)], vents=2),
                   [make_patient("P1", 5, 1.0, T0, vent=True)], T0 + timedelta(days=2))
    m = compute_metrics(eng, col)
    # 1 of 2 ventilators busy for 1 of 2 days
    assert m["ventilator_utilization"] == 0.25


def test_audit_flags_deliberately_invalid_allocations():
    state = make_state([("WARD-1", "WARD", False)], vents=1)
    p = make_patient("P1", 5, 1.0, T0, iso=True, vent=True)   # needs ICU+iso+vent
    eng = SimulationEngine(state, [p])
    p.status, p.bed_id, p.equipment_id = "DISCHARGED", "WARD-1", None
    p.admission_time, p.discharge_time = T0, T0 + timedelta(days=1)
    v = audit_violations(eng)
    assert v["acuity_tier"] == 1
    assert v["isolation"] == 1
    assert v["ventilator"] == 1
    assert v["total"] == 3


def test_audit_detects_double_booking():
    state = make_state([("ICU-1", "ICU", True)])
    a = make_patient("A", 5, 2.0, T0)
    b = make_patient("B", 5, 2.0, T0 + timedelta(days=1))
    eng = SimulationEngine(state, [a, b])
    for p in (a, b):
        p.status, p.bed_id = "DISCHARGED", "ICU-1"
        p.admission_time = p.arrival_time
        p.discharge_time = p.arrival_time + timedelta(days=2)   # overlap of 1 day
    assert audit_violations(eng)["double_booking"] == 1


def test_rule_based_baseline_has_zero_violations_on_mixed_load():
    state = make_state(
        [("ICU-1", "ICU", True), ("ICU-2", "ICU", False),
         ("SD-1", "STEP_DOWN", True), ("W-1", "WARD", False), ("W-2", "WARD", True)],
        vents=1)
    pts = [make_patient(f"P{i}", 1 + i % 5, 0.5 + (i % 3) * 0.3,
                        T0 + timedelta(hours=i), iso=(i % 4 == 0), vent=(i % 7 == 0 and i % 5 >= 3))
           for i in range(40)]
    eng, col = run(state, pts, T0 + timedelta(hours=40))
    assert audit_violations(eng)["total"] == 0
    assert eng.admitted_count == len(pts)
