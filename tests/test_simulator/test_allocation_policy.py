"""Unit tests for the shared allocation rules and the policy registry."""
from datetime import datetime

import pytest

from simulator.hospital import policy
from simulator.hospital.allocation_rules import (REASON_NO_BED, REASON_NO_VENTILATOR,
                                                 AllocationResult, candidate_bed_types,
                                                 decide_bed, evaluate_allocation)
from simulator.hospital.state import Bed, Equipment, HospitalState
from simulator.patients.patient import Patient


def state(beds, vents=()):
    s = HospitalState()
    for bed_id, btype, iso, *status in beds:
        s.beds[bed_id] = Bed(bed_id, btype, "W", status[0] if status else "AVAILABLE", iso)
    for eq_id in vents:
        s.equipment[eq_id] = Equipment(eq_id, "VENTILATOR", "AVAILABLE", "ICU")
    return s


def patient(acuity, iso=False, vent=False):
    return Patient("P", "45-64", acuity, "General", 2.0, iso, vent, datetime(2026, 1, 1))


def test_acuity_to_tier_table():
    assert candidate_bed_types(5) == ["ICU"]
    assert candidate_bed_types(4) == ["ICU", "STEP_DOWN"]
    assert candidate_bed_types(3) == ["STEP_DOWN", "WARD"]
    assert candidate_bed_types(2) == ["WARD"] == candidate_bed_types(1)


@pytest.mark.parametrize("bad", [0, 6, -1, None, "high"])
def test_invalid_acuity_is_rejected(bad):
    with pytest.raises(ValueError):
        candidate_bed_types(bad)


def test_escalation_and_reasons():
    s = state([("I1", "ICU", True, "OCCUPIED"), ("S1", "STEP_DOWN", True)])
    r = evaluate_allocation(patient(4), s)                    # ICU full -> step-down
    assert r.decision.bed_id == "S1" and r.reason == "Compatible STEP_DOWN bed available"
    r = evaluate_allocation(patient(5), s)                    # acuity 5 never leaves ICU
    assert r.decision is None and r.reason == REASON_NO_BED


def test_isolation_filter_and_lowest_id_tie_break():
    s = state([("W1", "WARD", False), ("W2", "WARD", True), ("W3", "WARD", True)])
    assert evaluate_allocation(patient(2, iso=True), s).decision.bed_id == "W2"
    assert evaluate_allocation(patient(2), s).decision.bed_id == "W1"


def test_ventilator_is_reserved_and_checked_first():
    s = state([("I1", "ICU", True)], vents=["V2", "V1"])
    d = evaluate_allocation(patient(5, vent=True), s).decision
    assert (d.bed_id, d.equipment_id) == ("I1", "V1")         # lowest ventilator id

    # no ventilator AND no bed: the ventilator reason wins (kept from the original API)
    empty = state([("I1", "ICU", True, "OCCUPIED")])
    r = evaluate_allocation(patient(5, vent=True), empty)
    assert r.decision is None and r.reason == REASON_NO_VENTILATOR


def test_evaluation_is_pure_and_decide_bed_agrees():
    s = state([("I1", "ICU", True)], vents=["V1"])
    p = patient(5, vent=True)
    r = evaluate_allocation(p, s)
    assert s.beds["I1"].status == "AVAILABLE" and s.equipment["V1"].status == "AVAILABLE"
    assert decide_bed(p, s) == r.decision


# ---------- policy registry ----------

@pytest.fixture()
def clean_registry():
    saved = dict(policy._POLICIES)
    yield
    policy._POLICIES.clear()
    policy._POLICIES.update(saved)


def test_default_algorithm_is_the_rule_baseline():
    s = state([("W1", "WARD", False)])
    assert policy.DEFAULT_ALGORITHM == "rule_based"
    assert policy.recommend(patient(1), s).decision.bed_id == "W1"


def test_unknown_algorithm_lists_the_available_ones():
    with pytest.raises(ValueError, match="rule_based"):
        policy.recommend(patient(1), state([]), "dqn")


def test_registered_policy_is_used(clean_registry):
    policy.register_policy("always_wait", lambda p, s: AllocationResult(None, "testing"))
    assert "always_wait" in policy.available_algorithms()
    r = policy.recommend(patient(1), state([("W1", "WARD", False)]), "always_wait")
    assert r.decision is None and r.reason == "testing"
