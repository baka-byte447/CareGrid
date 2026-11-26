"""API tests for /allocation/recommend and /allocation/approve.

The key test is the parity check: for hospitals in several different states the
API's recommendation must equal what the simulator's own `decide_bed` returns for
the same patient and the same state, so the backend can never silently drift from
the rules the RL agent is trained against."""
from datetime import datetime, timezone

import pytest

from backend.models import (
    AllocationRecommendation,
    AuditLog,
    Bed,
    BedAssignment,
    Encounter,
    Equipment,
    EquipmentAssignment,
    Patient,
    User,
)
from simulator.hospital.allocation_rules import decide_bed
from simulator.hospital.loader import load_hospital_state, load_patients

from .conftest import DATA_DIR

PATTERNS = ["empty", "icu_full", "no_ventilators", "no_isolation_beds", "half_full"]


def _pattern_sets(beds, vents, name):
    """-> (bed_ids to mark OCCUPIED, ventilator ids to mark IN_USE)"""
    beds = sorted(beds, key=lambda b: b.bed_id)
    vents = sorted(vents, key=lambda e: e.equipment_id)
    if name == "empty":
        return set(), set()
    if name == "icu_full":
        return {b.bed_id for b in beds if b.bed_type == "ICU"}, set()
    if name == "no_ventilators":
        return set(), {e.equipment_id for e in vents}
    if name == "no_isolation_beds":
        return {b.bed_id for b in beds if b.isolation_capable}, set()
    if name == "half_full":
        return ({b.bed_id for i, b in enumerate(beds) if i % 2 == 0},
                {e.equipment_id for i, e in enumerate(vents) if i % 2 == 0})
    raise AssertionError(name)


def _create_waiting_encounter(db_session, patient, **overrides):
    encounter = Encounter(
        patient_id=patient.patient_id,
        acuity=overrides.get("acuity", patient.acuity),
        specialty=overrides.get("specialty", patient.specialty),
        predicted_los=overrides.get("predicted_los", patient.predicted_los),
        isolation_required=overrides.get("isolation_required", patient.isolation_required),
        ventilator_required=overrides.get("ventilator_required", patient.ventilator_required),
        arrival_time=overrides.get("arrival_time", patient.arrival_time),
        status=overrides.get("status", "WAITING"),
    )
    db_session.add(encounter)
    db_session.commit()
    return encounter


def _request_recommendation(client, patient, algorithm="rule_based"):
    response = client.post("/allocation/recommend", json={
        "patient_id": patient.patient_id,
        "algorithm": algorithm,
    })
    assert response.status_code == 200, response.text
    return response.json()


def _approve_recommendation(client, recommendation, **extra):
    return client.post("/allocation/approve", json={
        "recommendation_id": recommendation["recommendation_id"],
        **extra,
    })


def _prepare_recommendation(client, db_session, patient, algorithm="rule_based"):
    encounter = _create_waiting_encounter(db_session, patient)
    response = _request_recommendation(client, patient, algorithm)
    assert response["status"] == "RECOMMENDED"
    return db_session.get(AllocationRecommendation, response["recommendation_id"]), response, encounter


@pytest.mark.parametrize("pattern", PATTERNS)
def test_api_recommendation_matches_simulator_rules(client, db_session, pattern):
    sim_state = load_hospital_state(DATA_DIR)            # same beds, started empty
    sim_patients = load_patients(DATA_DIR)

    occupied, in_use = _pattern_sets(sim_state.beds.values(),
                                     [e for e in sim_state.equipment.values()
                                      if e.type == "VENTILATOR"], pattern)
    for bed_id in occupied:
        sim_state.beds[bed_id].status = "OCCUPIED"
        db_session.get(Bed, bed_id).status = "OCCUPIED"
    for eq_id in in_use:
        sim_state.equipment[eq_id].status = "IN_USE"
        db_session.get(Equipment, eq_id).status = "IN_USE"
    db_session.commit()

    for patient in sim_patients[:250]:
        expected = decide_bed(patient, sim_state)
        body = client.post("/allocation/recommend",
                           json={"patient_id": patient.patient_id}).json()
        if expected is None:
            assert body["status"] == "NO_SUITABLE_BED", patient.patient_id
            assert body["recommended_bed_id"] is None
        else:
            assert body["status"] == "RECOMMENDED", patient.patient_id
            assert body["recommended_bed_id"] == expected.bed_id, patient.patient_id


def test_response_contract_and_reason_strings(client, db_session):
    # critical ventilated patient on an empty hospital -> ICU bed
    crit = (db_session.query(Patient)
            .filter(Patient.acuity == 5, Patient.ventilator_required.is_(True)).first())
    body = client.post("/allocation/recommend", json={"patient_id": crit.patient_id}).json()
    assert set(body) == {
        "recommendation_id", "patient_id", "recommended_bed_id", "algorithm", "reason", "status"
    }
    assert body["algorithm"] == "rule_based"
    assert body["status"] == "RECOMMENDED"
    assert body["reason"] == "Compatible ICU bed available"
    assert db_session.get(Bed, body["recommended_bed_id"]).bed_type == "ICU"
    saved = db_session.get(AllocationRecommendation, body["recommendation_id"])
    assert saved is not None
    assert saved.patient_id == crit.patient_id
    assert saved.status == "RECOMMENDED"
    assert saved.algorithm == "rule_based"
    assert saved.recommended_bed_id == body["recommended_bed_id"]
    assert saved.reason == body["reason"]
    assert saved.requested_by is not None

    # no ventilator free -> specific reason, no bed
    db_session.query(Equipment).filter(Equipment.type == "VENTILATOR").update(
        {Equipment.status: "IN_USE"})
    db_session.commit()
    body = client.post("/allocation/recommend", json={"patient_id": crit.patient_id}).json()
    assert body["status"] == "NO_SUITABLE_BED"
    assert body["reason"] == "No available ventilator"

    # no ICU bed free (and no ventilator needed) -> generic reason
    plain = (db_session.query(Patient)
             .filter(Patient.acuity == 5, Patient.ventilator_required.is_(False)).first())
    db_session.query(Bed).filter(Bed.bed_type == "ICU").update({Bed.status: "OCCUPIED"})
    db_session.commit()
    body = client.post("/allocation/recommend", json={"patient_id": plain.patient_id}).json()
    assert body["status"] == "NO_SUITABLE_BED"
    assert body["reason"] == "No compatible available bed found"


def test_recommend_error_cases(client, db_session):
    assert client.post("/allocation/recommend", json={"patient_id": "NOPE"}).status_code == 404

    p = db_session.query(Patient).first()
    p.acuity = 9
    db_session.commit()
    r = client.post("/allocation/recommend", json={"patient_id": p.patient_id})
    assert r.status_code == 400 and r.json()["detail"] == "Invalid patient acuity"

    p.acuity = 3
    p.current_status = "ADMITTED"
    db_session.commit()
    assert client.post("/allocation/recommend", json={"patient_id": p.patient_id}).status_code == 409


def test_approve_accepts_every_recommendation_the_api_makes(client, db_session):
    """Recommend and approve must agree on what is a valid bed. Sequentially admit
    patients (the hospital fills up as we go) and require every recommendation to
    be approvable."""
    patients = [
        p for p in load_patients(DATA_DIR)
        if db_session.get(Patient, p.patient_id).current_status.upper() == "WAITING"
    ][:150]
    for p in patients:
        _create_waiting_encounter(db_session, db_session.get(Patient, p.patient_id))

    approved = 0
    for p in patients:
        rec = _request_recommendation(client, db_session.get(Patient, p.patient_id))
        if rec["status"] != "RECOMMENDED":
            continue
        r = _approve_recommendation(client, rec)
        assert r.status_code == 200, (p.patient_id, r.json())
        approved += 1
    assert approved > 50


def test_approve_rejects_wrong_tier_and_non_isolation_beds(client, db_session):
    crit = db_session.query(Patient).filter(
    Patient.current_status == "WAITING",
    Patient.acuity == 5,
    Patient.ventilator_required.is_(False),
    Patient.isolation_required.is_(False),
).first()
    _create_waiting_encounter(db_session, crit)
    recommendation = _request_recommendation(client, crit)
    ward = db_session.query(Bed).filter(
        Bed.bed_type == "WARD", Bed.status == "AVAILABLE"
    ).first()
    db_session.get(AllocationRecommendation, recommendation["recommendation_id"]).recommended_bed_id = ward.bed_id
    db_session.commit()
    r = _approve_recommendation(client, recommendation)
    assert r.status_code == 400
    assert r.json()["detail"] == "Bed type is incompatible with encounter acuity"

    iso = db_session.query(Patient).filter(
    Patient.current_status == "WAITING",
    Patient.acuity == 1,
    Patient.isolation_required.is_(True),
).first()
    plain_ward = db_session.query(Bed).filter(Bed.bed_type == "WARD",
                                              Bed.isolation_capable.is_(False),
                                              Bed.status == "AVAILABLE").first()
    _create_waiting_encounter(db_session, iso)
    recommendation = _request_recommendation(client, iso)
    db_session.get(AllocationRecommendation, recommendation["recommendation_id"]).recommended_bed_id = plain_ward.bed_id
    db_session.commit()
    r = _approve_recommendation(client, recommendation)
    assert r.status_code == 400
    assert r.json()["detail"] == "Encounter requires an isolation-capable bed"


def test_approve_rule_based_recommendation_records_assignments_and_traceability(client, db_session):
    patient = db_session.query(Patient).filter(
        Patient.current_status == "WAITING",
        Patient.acuity == 5,
        Patient.ventilator_required.is_(True),
    ).first()
    recommendation, response, encounter = _prepare_recommendation(client, db_session, patient)
    original_reason = recommendation.reason
    original_q_values = recommendation.q_values
    doctor_id = db_session.query(User).filter(User.username == "test_doctor").one().id

    approved = _approve_recommendation(
        client,
        response,
        patient_id=patient.patient_id,
        bed_id=response["recommended_bed_id"],
    )
    assert approved.status_code == 200, approved.text
    assert approved.json() == {
        "patient_id": patient.patient_id,
        "bed_id": response["recommended_bed_id"],
        "status": "APPROVED",
    }

    db_session.refresh(recommendation)
    db_session.refresh(patient)
    db_session.refresh(encounter)
    bed_assignment = db_session.query(BedAssignment).filter(
        BedAssignment.encounter_id == encounter.encounter_id,
        BedAssignment.released_at.is_(None),
    ).one()
    equipment_assignment = db_session.query(EquipmentAssignment).filter(
        EquipmentAssignment.encounter_id == encounter.encounter_id,
        EquipmentAssignment.released_at.is_(None),
    ).one()
    assert bed_assignment.bed_id == response["recommended_bed_id"]
    assert bed_assignment.assigned_by == doctor_id
    assert equipment_assignment.assigned_by == doctor_id
    assigned_equipment = db_session.get(Equipment, equipment_assignment.equipment_id)
    assert assigned_equipment.type == "VENTILATOR"
    assert assigned_equipment.status == "IN_USE"
    assert recommendation.decision_status == "APPROVED"
    assert recommendation.decided_by == doctor_id
    assert recommendation.decided_at is not None
    assert recommendation.consumed_at is None
    assert recommendation.status == "RECOMMENDED"
    assert recommendation.reason == original_reason
    assert recommendation.q_values == original_q_values
    assert patient.current_status == "ADMITTED"
    assert encounter.status == "ADMITTED"
    audit = db_session.query(AuditLog).filter(
        AuditLog.patient_id == patient.patient_id,
        AuditLog.bed_id == response["recommended_bed_id"],
        AuditLog.action == "APPROVED",
    ).one()
    assert audit.algorithm == recommendation.algorithm
    assert _approve_recommendation(client, response).status_code == 409


def test_approve_dqn_safe_recommendation_revalidates_safety(client, db_session):
    patients = db_session.query(Patient).filter(
        Patient.current_status == "WAITING"
    ).order_by(Patient.patient_id).limit(40).all()
    chosen = None
    for patient in patients:
        _create_waiting_encounter(db_session, patient)
        result = _request_recommendation(client, patient, "dqn_safe")
        if result["algorithm"] == "dqn_safe" and result["status"] == "RECOMMENDED":
            chosen = (patient, result)
            break
    assert chosen is not None, "Expected at least one safe DQN bed recommendation"
    patient, result = chosen
    encounter = db_session.query(Encounter).filter(
        Encounter.patient_id == patient.patient_id,
        Encounter.status == "WAITING",
    ).one()
    recommendation = db_session.get(AllocationRecommendation, result["recommendation_id"])
    original_metadata = {
        "algorithm": recommendation.algorithm,
        "status": recommendation.status,
        "recommended_bed_id": recommendation.recommended_bed_id,
        "proposed_action": recommendation.proposed_action,
        "final_action": recommendation.final_action,
        "proposed_bed_type": recommendation.proposed_bed_type,
        "final_bed_type": recommendation.final_bed_type,
        "safety_overridden": recommendation.safety_overridden,
        "safety_rule_triggered": recommendation.safety_rule_triggered,
        "safety_original_action": recommendation.safety_original_action,
        "safety_reason": recommendation.safety_reason,
        "q_values": recommendation.q_values,
        "reason": recommendation.reason,
    }

    approved = _approve_recommendation(client, result)
    assert approved.status_code == 200, approved.text
    db_session.refresh(recommendation)
    assert recommendation.decision_status == "APPROVED"
    assert {
        "algorithm": recommendation.algorithm,
        "status": recommendation.status,
        "recommended_bed_id": recommendation.recommended_bed_id,
        "proposed_action": recommendation.proposed_action,
        "final_action": recommendation.final_action,
        "proposed_bed_type": recommendation.proposed_bed_type,
        "final_bed_type": recommendation.final_bed_type,
        "safety_overridden": recommendation.safety_overridden,
        "safety_rule_triggered": recommendation.safety_rule_triggered,
        "safety_original_action": recommendation.safety_original_action,
        "safety_reason": recommendation.safety_reason,
        "q_values": recommendation.q_values,
        "reason": recommendation.reason,
    } == original_metadata
    assert db_session.query(BedAssignment).filter(
        BedAssignment.encounter_id == encounter.encounter_id,
        BedAssignment.bed_id == recommendation.recommended_bed_id,
    ).count() == 1


def test_approve_rejects_missing_recommendation(client):
    response = client.post("/allocation/approve", json={"recommendation_id": 999999})
    assert response.status_code == 404


def test_approve_rejects_recommendation_without_encounter(client, db_session):
    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    recommendation = _request_recommendation(client, patient)
    saved = db_session.get(AllocationRecommendation, recommendation["recommendation_id"])
    assert saved.encounter_id is None

    response = _approve_recommendation(client, recommendation)
    assert response.status_code == 409
    assert "not linked to an Encounter" in response.json()["detail"]


def test_approve_rejects_client_patient_or_bed_mismatch(client, db_session):
    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    other = db_session.query(Patient).filter(
        Patient.current_status == "WAITING",
        Patient.patient_id != patient.patient_id,
    ).first()
    recommendation, _result, _encounter = _prepare_recommendation(client, db_session, patient)
    different_bed = db_session.query(Bed).filter(
        Bed.bed_id != recommendation.recommended_bed_id,
        Bed.status == "AVAILABLE",
    ).first()

    patient_mismatch = client.post("/allocation/approve", json={
        "recommendation_id": recommendation.recommendation_id,
        "patient_id": other.patient_id,
    })
    assert patient_mismatch.status_code == 409
    bed_mismatch = client.post("/allocation/approve", json={
        "recommendation_id": recommendation.recommendation_id,
        "bed_id": different_bed.bed_id,
    })
    assert bed_mismatch.status_code == 409
    db_session.refresh(recommendation)
    assert recommendation.decision_status is None


def test_approve_rejects_encounter_for_another_patient(client, db_session):
    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    other = db_session.query(Patient).filter(
        Patient.current_status == "WAITING",
        Patient.patient_id != patient.patient_id,
    ).first()
    recommendation, response, _encounter = _prepare_recommendation(client, db_session, patient)
    other_encounter = _create_waiting_encounter(db_session, other)
    recommendation.encounter_id = other_encounter.encounter_id
    db_session.commit()

    approved = _approve_recommendation(client, response)
    assert approved.status_code == 409
    assert "different patient" in approved.json()["detail"]


def test_approve_rejects_encounter_no_longer_waiting(client, db_session):
    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    recommendation, response, encounter = _prepare_recommendation(client, db_session, patient)
    encounter.status = "DISCHARGED"
    db_session.commit()

    approved = _approve_recommendation(client, response)
    assert approved.status_code == 409
    db_session.refresh(recommendation)
    assert recommendation.decision_status is None


@pytest.mark.parametrize("decision_status", ["REJECTED", "APPROVED"])
def test_approve_rejects_already_decided_recommendation(client, db_session, decision_status):
    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    recommendation, response, _encounter = _prepare_recommendation(client, db_session, patient)
    recommendation.decision_status = decision_status
    recommendation.decision_reason = "Existing decision"
    recommendation.decided_at = datetime.now(timezone.utc)
    db_session.commit()

    approved = _approve_recommendation(client, response)
    assert approved.status_code == 409
    db_session.refresh(recommendation)
    assert recommendation.decision_status == decision_status


def test_approve_rejects_consumed_recommendation(client, db_session):
    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    recommendation, response, _encounter = _prepare_recommendation(client, db_session, patient)
    recommendation.consumed_at = datetime.now(timezone.utc)
    db_session.commit()

    approved = _approve_recommendation(client, response)
    assert approved.status_code == 409
    assert "consumed" in approved.json()["detail"]


def test_approve_rejects_unavailable_bed_without_partial_changes(client, db_session):
    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    recommendation, response, encounter = _prepare_recommendation(client, db_session, patient)
    bed = db_session.get(Bed, recommendation.recommended_bed_id)
    bed.status = "OCCUPIED"
    db_session.commit()

    approved = _approve_recommendation(client, response)
    assert approved.status_code == 409
    db_session.refresh(recommendation)
    db_session.refresh(patient)
    assert recommendation.decision_status is None
    assert patient.current_status == "WAITING"
    assert db_session.query(BedAssignment).filter(
        BedAssignment.encounter_id == encounter.encounter_id
    ).count() == 0


def test_approve_rejects_when_required_ventilator_unavailable(client, db_session):
    patient = db_session.query(Patient).filter(
        Patient.current_status == "WAITING",
        Patient.ventilator_required.is_(True),
    ).first()
    recommendation, response, encounter = _prepare_recommendation(client, db_session, patient)
    db_session.query(Equipment).filter(Equipment.type == "VENTILATOR").update(
        {Equipment.status: "IN_USE"}
    )
    db_session.commit()

    approved = _approve_recommendation(client, response)
    assert approved.status_code == 409
    db_session.refresh(recommendation)
    assert recommendation.decision_status is None
    assert db_session.query(BedAssignment).filter(
        BedAssignment.encounter_id == encounter.encounter_id
    ).count() == 0


def test_approve_rejects_changed_dqn_safety_metadata(client, db_session):
    patients = db_session.query(Patient).filter(
        Patient.current_status == "WAITING"
    ).order_by(Patient.patient_id).limit(40).all()
    prepared = None
    for patient in patients:
        encounter = _create_waiting_encounter(db_session, patient)
        response = _request_recommendation(client, patient, "dqn_safe")
        if response["algorithm"] == "dqn_safe" and response["status"] == "RECOMMENDED":
            prepared = (patient, encounter, response)
            break
    if prepared is None:
        pytest.skip("No successful DQN result available for safety revalidation")
    patient, _encounter, response = prepared
    recommendation = db_session.get(AllocationRecommendation, response["recommendation_id"])
    recommendation.safety_reason = "altered safety result"
    db_session.commit()

    approved = _approve_recommendation(client, response)
    assert approved.status_code == 409
    assert "safety validation" in approved.json()["detail"]
    db_session.refresh(recommendation)
    assert recommendation.decision_status is None


def test_approve_requires_authorized_user(unauthenticated_client, db_session):
    from backend.auth.security import create_access_token

    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    encounter = _create_waiting_encounter(db_session, patient)
    bed = db_session.query(Bed).filter(Bed.status == "AVAILABLE").first()
    recommendation = AllocationRecommendation(
        patient_id=patient.patient_id,
        encounter_id=encounter.encounter_id,
        algorithm="rule_based",
        status="RECOMMENDED",
        recommended_bed_id=bed.bed_id,
        reason="Test recommendation",
    )
    db_session.add(recommendation)
    db_session.commit()

    response = unauthenticated_client.post("/allocation/approve", json={
        "recommendation_id": recommendation.recommendation_id,
    })
    assert response.status_code == 401

    nurse = User(
        username="test_nurse_approve",
        email="test_nurse_approve@example.com",
        hashed_password="test-hash",
        role="nurse",
        is_active=True,
    )
    db_session.add(nurse)
    db_session.commit()
    unauthenticated_client.headers["Authorization"] = (
        "Bearer " + create_access_token(data={"sub": str(nurse.id), "role": nurse.role})
    )
    forbidden = unauthenticated_client.post("/allocation/approve", json={
        "recommendation_id": recommendation.recommendation_id,
    })
    assert forbidden.status_code == 403


def test_approve_rolls_back_lifecycle_writes_if_finalization_fails(client, db_session, monkeypatch):
    import backend.api.main as api_main
    from backend.services.patient_lifecycle import LifecycleConflict

    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    recommendation, response, encounter = _prepare_recommendation(client, db_session, patient)
    bed_id = recommendation.recommended_bed_id
    original_approve = api_main.approve_encounter

    def fail_after_lifecycle_flush(*args, **kwargs):
        original_approve(*args, **kwargs)
        raise LifecycleConflict("injected finalization failure")

    monkeypatch.setattr(api_main, "approve_encounter", fail_after_lifecycle_flush)
    approved = _approve_recommendation(client, response)
    assert approved.status_code == 409
    db_session.refresh(recommendation)
    db_session.refresh(patient)
    db_session.refresh(encounter)
    assert recommendation.decision_status is None
    assert patient.current_status == "WAITING"
    assert encounter.status == "WAITING"
    assert db_session.get(Bed, bed_id).status == "AVAILABLE"
    assert db_session.query(BedAssignment).filter(
        BedAssignment.encounter_id == encounter.encounter_id
    ).count() == 0
    assert db_session.query(AuditLog).filter(
        AuditLog.patient_id == patient.patient_id,
        AuditLog.action.in_(("ADMITTED", "APPROVED")),
    ).count() == 0


def test_recommend_dqn_safe_algorithm(client, db_session):
    p = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    r = client.post("/allocation/recommend", json={"patient_id": p.patient_id, "algorithm": "dqn_safe"})
    assert r.status_code == 200
    body = r.json()
    assert body["patient_id"] == p.patient_id
    assert body["algorithm"] == "dqn_safe"
    assert "safety" in body
    assert "q_values" in body
    assert "los_estimate_days" in body
    assert body["safety"]["overridden"] in (True, False)
    saved = db_session.get(AllocationRecommendation, body["recommendation_id"])
    assert saved is not None
    assert saved.algorithm == body["algorithm"]
    assert saved.status == body["status"]
    assert saved.q_values == body["q_values"]
    assert saved.proposed_action == body["proposed_action"]
    assert saved.final_action == body["final_action"]
    assert saved.safety_overridden == body["safety"]["overridden"]


def test_no_suitable_bed_recommendation_is_persisted(client, db_session):
    p = db_session.query(Patient).filter(
        Patient.current_status == "WAITING",
        Patient.ventilator_required.is_(False),
    ).first()
    db_session.query(Bed).update({Bed.status: "OCCUPIED"})
    db_session.commit()

    response = client.post("/allocation/recommend", json={"patient_id": p.patient_id})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "NO_SUITABLE_BED"
    assert body["recommended_bed_id"] is None

    saved = db_session.get(AllocationRecommendation, body["recommendation_id"])
    assert saved is not None
    assert saved.patient_id == p.patient_id
    assert saved.status == "NO_SUITABLE_BED"
    assert saved.recommended_bed_id is None


def test_safety_intervention_is_persisted(client, db_session, monkeypatch):
    from types import SimpleNamespace

    import backend.api.main as api_main

    p = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    safety = {"overridden": True, "rule_triggered": "test_guardrail", "original_action": 3,
              "reason": "Safety layer selected a feasible fallback"}
    result = SimpleNamespace(
        recommended_bed_id=None,
        algorithm="dqn_safe",
        reasons=[safety["reason"]],
        status="WAIT",
        safety=SimpleNamespace(to_dict=lambda: safety),
        q_values=[0.1, 0.2, 0.3, 0.9],
        los_estimate_days=4.0,
        proposed_action=3,
        final_action=1,
        proposed_bed_type="WAIT",
        final_bed_type="STEP_DOWN",
    )

    class FakeAllocationService:
        def recommend(self, *_args, **_kwargs):
            return result

    monkeypatch.setattr(api_main, "get_allocation_service", lambda: FakeAllocationService())
    response = client.post(
        "/allocation/recommend",
        json={"patient_id": p.patient_id, "algorithm": "dqn_safe"},
    )
    assert response.status_code == 200
    body = response.json()
    saved = db_session.get(AllocationRecommendation, body["recommendation_id"])
    assert saved is not None
    assert saved.safety_overridden is True
    assert saved.safety_rule_triggered == "test_guardrail"
    assert saved.safety_reason == safety["reason"]
    assert saved.proposed_action == 3
    assert saved.final_action == 1


def test_recommendation_links_unique_waiting_encounter(client, db_session):
    from backend.models import Encounter

    p = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    encounter = Encounter(
        patient_id=p.patient_id,
        acuity=p.acuity,
        specialty=p.specialty,
        predicted_los=p.predicted_los,
        isolation_required=p.isolation_required,
        ventilator_required=p.ventilator_required,
        arrival_time=p.arrival_time,
        status="WAITING",
    )
    db_session.add(encounter)
    db_session.commit()

    response = client.post("/allocation/recommend", json={"patient_id": p.patient_id})
    assert response.status_code == 200
    saved = db_session.get(AllocationRecommendation, response.json()["recommendation_id"])
    assert saved.encounter_id == encounter.encounter_id


def _create_rejectable_recommendation(db_session, patient):
    bed = db_session.query(Bed).order_by(Bed.bed_id).first()
    recommendation = AllocationRecommendation(
        patient_id=patient.patient_id,
        algorithm="dqn_safe",
        status="RECOMMENDED",
        recommended_bed_id=bed.bed_id,
        proposed_action=2,
        final_action=2,
        proposed_bed_type="WARD",
        final_bed_type="WARD",
        safety_overridden=False,
        safety_rule_triggered=None,
        safety_original_action=2,
        safety_reason=None,
        q_values=[0.1, 0.2, 0.7, 0.0],
        model_version=None,
        reason="Compatible bed available",
    )
    db_session.add(recommendation)
    db_session.commit()
    db_session.refresh(recommendation)
    return recommendation


def test_reject_allocation(client, db_session):
    p = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    recommendation = _create_rejectable_recommendation(db_session, p)
    original = {
        "algorithm": recommendation.algorithm,
        "status": recommendation.status,
        "recommended_bed_id": recommendation.recommended_bed_id,
        "q_values": recommendation.q_values,
        "safety_overridden": recommendation.safety_overridden,
        "reason": recommendation.reason,
    }
    doctor_id = db_session.query(User).filter(User.role == "doctor").first().id
    before_decision = datetime.now(timezone.utc).replace(tzinfo=None)
    r = client.post("/allocation/reject", json={
        "recommendation_id": recommendation.recommendation_id,
        "patient_id": p.patient_id,
        "reason": "Clinical contraindication",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["recommendation_id"] == recommendation.recommendation_id
    assert data["patient_id"] == p.patient_id
    assert data["status"] == "REJECTED"
    assert data["reason"] == "Clinical contraindication"

    db_session.refresh(recommendation)
    assert recommendation.decision_status == "REJECTED"
    assert recommendation.decision_reason == "Clinical contraindication"
    assert recommendation.decided_by == doctor_id
    assert recommendation.decided_at is not None
    decided_at = recommendation.decided_at
    if decided_at.tzinfo is not None:
        decided_at = decided_at.astimezone(timezone.utc).replace(tzinfo=None)
    assert before_decision <= decided_at <= datetime.now(timezone.utc).replace(tzinfo=None)
    assert recommendation.consumed_at is None
    assert {
        "algorithm": recommendation.algorithm,
        "status": recommendation.status,
        "recommended_bed_id": recommendation.recommended_bed_id,
        "q_values": recommendation.q_values,
        "safety_overridden": recommendation.safety_overridden,
        "reason": recommendation.reason,
    } == original

    audit = db_session.query(AuditLog).filter(
        AuditLog.patient_id == p.patient_id,
        AuditLog.action == "REJECTED",
    ).one()
    assert audit is not None
    assert audit.algorithm == "operator_override"
    assert audit.bed_id == recommendation.recommended_bed_id


def test_reject_allocation_validation(client, db_session):
    # Nonexistent recommendation -> 404
    r = client.post("/allocation/reject", json={
        "recommendation_id": 999999,
        "reason": "Clinical contraindication",
    })
    assert r.status_code == 404

    # Validation: reason too short -> 422
    r = client.post("/allocation/reject", json={
        "recommendation_id": 1,
        "reason": "no",
    })
    assert r.status_code == 422

    # Missing and whitespace-only reasons are also rejected before route execution.
    r = client.post("/allocation/reject", json={"recommendation_id": 1})
    assert r.status_code == 422
    r = client.post("/allocation/reject", json={
        "recommendation_id": 1,
        "reason": "   ",
    })
    assert r.status_code == 422


def test_reject_allocation_patient_mismatch(client, db_session):
    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    other_patient = db_session.query(Patient).filter(
        Patient.patient_id != patient.patient_id,
        Patient.current_status == "WAITING",
    ).first()
    recommendation = _create_rejectable_recommendation(db_session, patient)

    response = client.post("/allocation/reject", json={
        "recommendation_id": recommendation.recommendation_id,
        "patient_id": other_patient.patient_id,
        "reason": "Clinical contraindication",
    })
    assert response.status_code == 409
    db_session.refresh(recommendation)
    assert recommendation.decision_status is None
    assert db_session.query(AuditLog).filter(AuditLog.action == "REJECTED").count() == 0


def test_reject_allocation_duplicate_decision_conflicts(client, db_session):
    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    recommendation = _create_rejectable_recommendation(db_session, patient)
    payload = {
        "recommendation_id": recommendation.recommendation_id,
        "reason": "Clinical contraindication",
    }
    assert client.post("/allocation/reject", json=payload).status_code == 200

    duplicate = client.post("/allocation/reject", json=payload)
    assert duplicate.status_code == 409
    db_session.refresh(recommendation)
    assert recommendation.decision_status == "REJECTED"
    assert db_session.query(AuditLog).filter(AuditLog.action == "REJECTED").count() == 1


def test_reject_allocation_requires_authorized_user(unauthenticated_client, db_session):
    from backend.auth.security import create_access_token

    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    recommendation = _create_rejectable_recommendation(db_session, patient)
    assert unauthenticated_client.post("/allocation/reject", json={
        "recommendation_id": recommendation.recommendation_id,
        "reason": "Clinical contraindication",
    }).status_code == 401

    nurse = User(
        username="test_nurse_reject",
        email="test_nurse_reject@example.com",
        hashed_password="test-hash",
        role="nurse",
        is_active=True,
    )
    db_session.add(nurse)
    db_session.commit()
    unauthenticated_client.headers["Authorization"] = (
        "Bearer " + create_access_token(data={"sub": str(nurse.id), "role": nurse.role})
    )
    response = unauthenticated_client.post("/allocation/reject", json={
        "recommendation_id": recommendation.recommendation_id,
        "reason": "Clinical contraindication",
    })
    assert response.status_code == 403
    db_session.refresh(recommendation)
    assert recommendation.decision_status is None


def test_reject_allocation_requires_recommended_bed(client, db_session):
    patient = db_session.query(Patient).filter(Patient.current_status == "WAITING").first()
    recommendation = AllocationRecommendation(
        patient_id=patient.patient_id,
        algorithm="rule_based",
        status="NO_SUITABLE_BED",
        recommended_bed_id=None,
        reason="No compatible available bed found",
    )
    db_session.add(recommendation)
    db_session.commit()

    response = client.post("/allocation/reject", json={
        "recommendation_id": recommendation.recommendation_id,
        "reason": "No bed can be accepted",
    })
    assert response.status_code == 409
    db_session.refresh(recommendation)
    assert recommendation.decision_status is None
