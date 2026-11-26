"""Tests for Milestone 2C: simulated time consistency, G2 guardrails, and encounter reconciliation."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.database import Base
from backend.models import Bed, Encounter, Patient
from backend.reconcile_encounters import reconcile
from backend.services.hospital_state import build_hospital_state, to_simulator_patient
from backend.services.patient_lifecycle import approve_encounter
from rl.environment.observation import build_observation
from safety.layer import SafetyConfig, SafetyLayer
from safety.rules import WAIT_ACTION
from simulator.hospital.state import Bed as SimBed
from simulator.hospital.state import HospitalState
from simulator.patients.patient import Patient as SimPatient


def test_build_hospital_state_uses_simulated_time(db_session):
    """state.current_time must match max(Patient.arrival_time), not wall-clock UTC."""
    max_arrival = db_session.query(func.max(Patient.arrival_time)).scalar()
    assert max_arrival is not None

    state = build_hospital_state(db_session)
    assert state.current_time == max_arrival.replace(tzinfo=None)
    assert state.current_time.tzinfo is None


def test_build_hospital_state_empty_db_falls_back_to_utc():
    """Empty DB falls back to naive UTC now without crashing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        state = build_hospital_state(session)
        after = datetime.now(timezone.utc).replace(tzinfo=None)
        assert state.current_time is not None
        assert state.current_time.tzinfo is None
        assert before <= state.current_time <= after
    finally:
        session.close()
        engine.dispose()


def test_g2_guardrail_fires_correctly_with_simulated_time():
    """Acuity-2 patient waiting 96h (> 72h G2 threshold) on simulated clock triggers G2."""
    state = HospitalState(current_time=datetime(2026, 10, 5, 10, 0, 0))
    state.beds["B_WARD_1"] = SimBed(
        bed_id="B_WARD_1",
        bed_type="WARD",
        ward="Ward-A",
        status="AVAILABLE",
        isolation_capable=False,
    )
    patient = SimPatient(
        patient_id="P_G2_TEST",
        age_group="36-50",
        acuity=2,
        specialty="General",
        predicted_los=3.0,
        isolation_required=False,
        ventilator_required=False,
        arrival_time=datetime(2026, 10, 1, 10, 0, 0),  # 96h elapsed
    )

    layer = SafetyLayer(SafetyConfig(guardrails=True))
    decision = layer.review(patient, state, proposed_action=WAIT_ACTION)

    assert decision.status == "OVERRIDDEN"
    assert decision.guardrail_triggered == "G2_MAX_WAIT"
    assert decision.final_action != WAIT_ACTION


def test_g2_guardrail_does_not_fire_for_fresh_arrival():
    """Acuity-2 patient waiting 1h (< 72h G2 threshold) is not overridden by G2."""
    state = HospitalState(current_time=datetime(2026, 10, 5, 10, 0, 0))
    state.beds["B_WARD_1"] = SimBed(
        bed_id="B_WARD_1",
        bed_type="WARD",
        ward="Ward-A",
        status="AVAILABLE",
        isolation_capable=False,
    )
    patient = SimPatient(
        patient_id="P_FRESH_TEST",
        age_group="36-50",
        acuity=2,
        specialty="General",
        predicted_los=3.0,
        isolation_required=False,
        ventilator_required=False,
        arrival_time=datetime(2026, 10, 5, 9, 0, 0),  # 1h elapsed
    )

    layer = SafetyLayer(SafetyConfig(guardrails=True))
    decision = layer.review(patient, state, proposed_action=WAIT_ACTION)

    assert decision.status == "APPROVED"
    assert decision.final_action == WAIT_ACTION
    assert decision.guardrail_triggered is None


def test_wait_so_far_observation_uses_simulated_time():
    """build_observation v2 wait_so_far uses state.current_time when now is None."""
    state = HospitalState(current_time=datetime(2026, 10, 4, 12, 0, 0))
    state.beds["B_WARD_1"] = SimBed(
        bed_id="B_WARD_1",
        bed_type="WARD",
        ward="Ward-A",
        status="AVAILABLE",
        isolation_capable=False,
    )
    patient = SimPatient(
        patient_id="P_OBS_TEST",
        age_group="36-50",
        acuity=2,
        specialty="General",
        predicted_los=3.0,
        isolation_required=False,
        ventilator_required=False,
        arrival_time=datetime(2026, 10, 1, 0, 0, 0),  # 3.5 days -> 3.5 / 7.0 = 0.5
    )

    obs = build_observation(patient, state, los_estimate=3.0, now=None, version=2)
    assert obs.shape == (17,)
    assert obs[14] == pytest.approx(0.5, abs=1e-5)


def test_import_creates_waiting_encounters_and_reconcile_is_idempotent(db_session):
    """CSV import creates WAITING Encounters; reconcile backfills missing ones idempotently."""
    waiting_patients = (
        db_session.query(Patient)
        .filter(Patient.current_status == "WAITING")
        .count()
    )
    waiting_encounters = (
        db_session.query(Encounter)
        .filter(Encounter.status == "WAITING")
        .count()
    )
    assert waiting_patients > 0
    assert waiting_encounters == waiting_patients

    # Simulate a legacy WAITING patient missing an Encounter
    sample_enc = (
        db_session.query(Encounter)
        .filter(Encounter.status == "WAITING")
        .first()
    )
    assert sample_enc is not None
    target_pid = sample_enc.patient_id
    db_session.delete(sample_enc)
    db_session.commit()

    first_run = reconcile(db_session)
    assert first_run["encounters_created"] == 1

    restored = (
        db_session.query(Encounter)
        .filter(Encounter.patient_id == target_pid, Encounter.status == "WAITING")
        .first()
    )
    assert restored is not None

    # Second run must be a no-op
    second_run = reconcile(db_session)
    assert second_run["encounters_created"] == 0


def test_build_hospital_state_populates_admitted_patients(db_session):
    """Admitted patients with active BedAssignments appear in state.admitted_patients."""
    patient = (
        db_session.query(Patient)
        .filter(
            Patient.current_status == "WAITING",
            Patient.acuity <= 2,
            Patient.isolation_required.is_(False),
            Patient.ventilator_required.is_(False),
        )
        .first()
    )
    assert patient is not None

    bed = (
        db_session.query(Bed)
        .filter(Bed.status == "AVAILABLE", Bed.bed_type == "WARD")
        .first()
    )
    assert bed is not None

    encounter = (
        db_session.query(Encounter)
        .filter(Encounter.patient_id == patient.patient_id, Encounter.status == "WAITING")
        .first()
    )
    assert encounter is not None

    approve_encounter(db_session, encounter_id=encounter.encounter_id, bed_id=bed.bed_id)
    db_session.commit()

    state = build_hospital_state(db_session)
    assert state.admitted_patients.get(patient.patient_id) == bed.bed_id
    assert patient.patient_id not in state.waiting_queue
