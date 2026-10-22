"""Engine safety and event-ordering tests for external-decision mode."""
from datetime import datetime, timedelta

import pytest

from simulator.hospital.allocation_rules import AllocationDecision, AllocationValidationError
from simulator.hospital.engine import SimulationEngine
from simulator.hospital.state import Bed, Equipment, HospitalState
from simulator.patients.patient import Patient

T0 = datetime(2026, 1, 1, 8, 0, 0)


def patient(pid="p1", acuity=1, isolation=False, ventilator=False, los=2.0, arrival=T0):
    return Patient(pid, "18-64", acuity, "GENERAL", los, isolation, ventilator, arrival)


def state_with_resources():
    return HospitalState(
        beds={
            "WARD-01": Bed("WARD-01", "WARD", "A", "AVAILABLE", True),
            "WARD-02": Bed("WARD-02", "WARD", "A", "OCCUPIED", True),
            "WARD-ISO": Bed("WARD-ISO", "WARD", "B", "AVAILABLE", False),
            "ICU-01": Bed("ICU-01", "ICU", "ICU", "AVAILABLE", True),
            "STEP-01": Bed("STEP-01", "STEP_DOWN", "S", "AVAILABLE", True),
        },
        equipment={
            "VENT-01": Equipment("VENT-01", "VENTILATOR", "AVAILABLE", "ICU"),
            "VENT-BUSY": Equipment("VENT-BUSY", "VENTILATOR", "IN_USE", "ICU"),
            "MON-01": Equipment("MON-01", "MONITOR", "AVAILABLE", "WARD"),
        },
        current_time=T0,
    )


def pending_engine(patients=None, state=None):
    patients = patients or [patient()]
    state = state or state_with_resources()
    engine = SimulationEngine(state, patients)
    engine.enable_external_decisions()
    engine.seed_arrivals()
    assert engine.advance_to_decision() == patients[0].patient_id
    return engine


def resource_snapshot(engine):
    return {
        "beds": {key: (bed.status, bed.bed_type) for key, bed in engine.state.beds.items()},
        "equipment": {key: (item.status, item.type) for key, item in engine.state.equipment.items()},
        "waiting": list(engine.state.waiting_queue),
        "admitted": dict(engine.state.admitted_patients),
        "patient": vars(engine.patients[engine.pending_patient_id]).copy(),
        "admitted_count": engine.admitted_count,
        "discharged_count": engine.discharged_count,
        "queue_length": len(engine.queue),
        "pending": engine.pending_patient_id,
    }


@pytest.mark.parametrize(
    "patient_kwargs,decision,mutate_state,expected_reason",
    [
        ({}, AllocationDecision("WARD-02"), None, "bed_not_available"),
        ({}, AllocationDecision("MISSING"), None, "bed_not_found"),
        ({"acuity": 1}, AllocationDecision("ICU-01"), None, "bed_type_incompatible_with_acuity"),
        ({"isolation": True}, AllocationDecision("WARD-ISO"), None, "bed_not_isolation_capable"),
        ({"ventilator": True, "acuity": 5}, AllocationDecision("ICU-01"), None, "ventilator_required"),
        ({"ventilator": True, "acuity": 5}, AllocationDecision("ICU-01", "MISSING"), None, "equipment_not_found"),
        ({"ventilator": True, "acuity": 5}, AllocationDecision("ICU-01", "MON-01"), None, "equipment_not_a_ventilator"),
        ({"ventilator": True, "acuity": 5}, AllocationDecision("ICU-01", "VENT-BUSY"), None, "ventilator_unavailable"),
        ({}, AllocationDecision("WARD-01", "VENT-01"), None, "unneeded_equipment_must_not_be_reserved"),
    ],
)
def test_invalid_allocation_is_rejected_without_mutation(
    patient_kwargs, decision, mutate_state, expected_reason
):
    p = patient(**patient_kwargs)
    engine = pending_engine([p])
    before = resource_snapshot(engine)
    with pytest.raises(AllocationValidationError, match=expected_reason):
        engine.admit_pending_patient(decision)
    assert resource_snapshot(engine) == before


@pytest.mark.parametrize("eligibility_change,expected_reason", [
    ("discharged", "patient_already_discharged"),
    ("admitted", "patient_already_admitted"),
])
def test_duplicate_or_non_waiting_patient_cannot_be_admitted(eligibility_change, expected_reason):
    p = patient()
    engine = pending_engine([p])
    if eligibility_change == "discharged":
        p.status = "DISCHARGED"
    else:
        engine.state.admitted_patients[p.patient_id] = "WARD-02"
    before = resource_snapshot(engine)
    with pytest.raises(AllocationValidationError, match=expected_reason):
        engine.admit_pending_patient(AllocationDecision("WARD-01"))
    assert resource_snapshot(engine) == before


def test_run_is_rejected_in_external_decision_mode():
    engine = pending_engine()
    with pytest.raises(RuntimeError, match=r"run\(\) is unavailable in external-decision mode"):
        engine.run()


def test_multiple_same_time_arrivals_and_waits_are_processed_once():
    patients = [patient("A", arrival=T0), patient("B", arrival=T0), patient("C", arrival=T0)]
    state = state_with_resources()
    engine = pending_engine(patients, state)
    assert engine.pending_patient_id == "A"
    assert engine.defer_pending_patient() == "A"
    assert engine.advance_to_decision(max_time=T0) == "B"
    assert engine.defer_pending_patient() == "B"
    assert engine.advance_to_decision(max_time=T0) == "C"
    engine.admit_pending_patient(AllocationDecision("WARD-01"))
    assert engine.state.waiting_queue == ["A", "B"]
    assert engine.admitted_count == 1
    # No same-timestamp patient is presented repeatedly; later discharge is past max_time.
    assert engine.advance_to_decision(max_time=T0) is None
    assert engine.state.current_time == T0
    assert engine.state.waiting_queue == ["A", "B"]


def test_bed_release_offers_oldest_feasible_waiter_without_auto_admission():
    incompatible = patient("oldest", acuity=1)
    eligible_1 = patient("next", acuity=5)
    eligible_2 = patient("third", acuity=5)
    state = state_with_resources()
    # Keep only the ICU bed unavailable until the release event.
    state.beds["ICU-01"].status = "CLEANING"
    state.beds["WARD-01"].status = "OCCUPIED"
    state.beds["WARD-ISO"].status = "OCCUPIED"
    state.waiting_queue[:] = ["oldest", "next", "third"]
    engine = SimulationEngine(state, [incompatible, eligible_1, eligible_2])
    engine.enable_external_decisions()
    engine.queue.schedule(T0 + timedelta(minutes=5), "BED_RELEASE", {"bed_id": "ICU-01"})
    assert engine.advance_to_decision() == "next"
    assert state.beds["ICU-01"].status == "AVAILABLE"
    assert state.admitted_patients == {}
    assert engine.admitted_count == 0
    assert state.waiting_queue == ["oldest", "next", "third"]


def test_waiting_patient_is_not_duplicated_when_deferred_repeatedly():
    p = patient()
    engine = pending_engine([p])
    engine.defer_pending_patient()
    assert engine.state.waiting_queue == ["p1"]
    # No second pending decision exists until a later event makes the patient eligible.
    with pytest.raises(RuntimeError, match="There is no pending patient decision"):
        engine.defer_pending_patient()
    assert engine.state.waiting_queue == ["p1"]


def test_time_limit_does_not_pop_future_event_or_advance_clock_past_limit():
    p = patient(arrival=T0 + timedelta(days=2))
    state = state_with_resources()
    engine = SimulationEngine(state, [p])
    engine.enable_external_decisions()
    engine.seed_arrivals()
    limit = T0 + timedelta(days=1)
    before_length = len(engine.queue)
    assert engine.advance_to_decision(max_time=limit) is None
    assert state.current_time == limit
    assert len(engine.queue) == before_length
    assert engine.queue.peek().timestamp == p.arrival_time
    assert p.status == "WAITING"
    assert engine.admitted_count == 0
