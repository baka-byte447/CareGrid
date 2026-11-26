"""End-to-end API and role-permission tests for the hospital operational workflow."""
from datetime import datetime, timezone

import pytest

from backend.auth.security import create_access_token
from backend.models import (
    AuditLog,
    Bed,
    BedAssignment,
    Encounter,
    Equipment,
    EquipmentAssignment,
    Patient,
    User,
)
from backend.services.hospital_state import build_hospital_state


def _auth_headers(db_session, *, username: str, role: str) -> tuple[User, dict[str, str]]:
    existing = db_session.query(User).filter(User.username == username).first()
    if existing is None:
        user = User(
            username=username,
            email=f"{username}@example.com",
            hashed_password="test-hash",
            role=role,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    else:
        user = existing
    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return user, {"Authorization": f"Bearer {token}"}


def _pick_compatible_bed(db_session, *, bed_type: str, isolation: bool = False, exclude: set[str] | None = None) -> Bed:
    query = db_session.query(Bed).filter(
        Bed.status == "AVAILABLE",
        Bed.bed_type == bed_type,
    )
    if isolation:
        query = query.filter(Bed.isolation_capable.is_(True))
    if exclude:
        query = query.filter(~Bed.bed_id.in_(exclude))
    bed = query.order_by(Bed.bed_id).first()
    assert bed is not None
    return bed


def test_full_operational_workflow_lifecycle(client, db_session):
    """Intake -> Recommend -> Approve -> Equipment -> Transfer -> Cleaning -> Discharge."""
    nurse_user, nurse_headers = _auth_headers(db_session, username="wf_nurse", role="nurse")
    _, operator_headers = _auth_headers(db_session, username="wf_operator", role="operator")

    # 1. Nurse performs patient intake -> creates Patient + WAITING Encounter
    intake_resp = client.post(
        "/patients/intake",
        json={
            "patient_id": "WF0001",
            "age_group": "36-50",
            "acuity": 5,
            "specialty": "Pulmonology",
            "predicted_los": 4.5,
            "isolation_required": True,
            "ventilator_required": True,
        },
        headers=nurse_headers,
    )
    assert intake_resp.status_code == 201, intake_resp.text
    intake_data = intake_resp.json()
    assert intake_data["patient_id"] == "WF0001"
    assert intake_data["current_status"] == "WAITING"
    assert intake_data["encounter_status"] == "WAITING"
    encounter_id = intake_data["encounter_id"]

    encounter = db_session.get(Encounter, encounter_id)
    assert encounter is not None
    assert encounter.status == "WAITING"
    assert "WF0001" in build_hospital_state(db_session).waiting_queue

    # Duplicate intake while WAITING must be rejected (409)
    dup_resp = client.post(
        "/patients/intake",
        json={
            "patient_id": "WF0001",
            "age_group": "36-50",
            "acuity": 5,
            "specialty": "Pulmonology",
            "predicted_los": 4.5,
        },
        headers=nurse_headers,
    )
    assert dup_resp.status_code == 409

    # 2. Doctor recommends & approves admission -> uses Encounter + creates Bed/EquipmentAssignment
    rec_resp = client.post("/allocation/recommend", json={"patient_id": "WF0001"})
    assert rec_resp.status_code == 200
    bed_1_id = rec_resp.json()["recommended_bed_id"]
    assert bed_1_id is not None

    approve_resp = client.post(
        "/allocation/approve",
        json={"patient_id": "WF0001", "bed_id": bed_1_id},
    )
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json() == {
        "patient_id": "WF0001",
        "bed_id": bed_1_id,
        "status": "APPROVED",
    }

    db_session.expire_all()
    assert db_session.query(Encounter).filter_by(patient_id="WF0001").count() == 1
    encounter = db_session.get(Encounter, encounter_id)
    assert encounter.status == "ADMITTED"
    assert db_session.get(Patient, "WF0001").current_status == "ADMITTED"
    assert db_session.get(Bed, bed_1_id).status == "OCCUPIED"

    listed_beds = {bed["bed_id"]: bed for bed in client.get("/beds").json()["beds"]}
    assert listed_beds[bed_1_id]["patient_id"] == "WF0001"

    bed_assignments = db_session.query(BedAssignment).filter_by(encounter_id=encounter_id).all()
    assert len(bed_assignments) == 1
    assert bed_assignments[0].bed_id == bed_1_id
    assert bed_assignments[0].released_at is None
    assert bed_assignments[0].assigned_by is not None

    vent_assignments = db_session.query(EquipmentAssignment).filter_by(encounter_id=encounter_id).all()
    assert len(vent_assignments) == 1
    vent_id = vent_assignments[0].equipment_id
    assert db_session.get(Equipment, vent_id).status == "IN_USE"

    # Metrics must reflect the ADMITTED audit record in approved_allocations
    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert metrics_resp.json()["approved_allocations"] >= 1

    # 3. Nurse assigns an additional monitor, then releases it early
    monitor = Equipment(
        equipment_id="MON-WF01",
        type="TELEMETRY",
        status="AVAILABLE",
        location="ICU-Alpha",
    )
    db_session.add(monitor)
    db_session.commit()

    assign_resp = client.post(
        f"/equipment/{monitor.equipment_id}/assign",
        json={"patient_id": "WF0001"},
        headers=nurse_headers,
    )
    assert assign_resp.status_code == 200, assign_resp.text
    assign_body = assign_resp.json()
    assert assign_body["encounter_id"] == encounter_id
    assert assign_body["status"] == "IN_USE"
    assert db_session.get(Equipment, monitor.equipment_id).status == "IN_USE"

    release_resp = client.post(
        f"/equipment/{monitor.equipment_id}/release",
        json={"release_reason": "telemetry discontinued"},
        headers=nurse_headers,
    )
    assert release_resp.status_code == 200, release_resp.text
    assert release_resp.json()["status"] == "AVAILABLE"
    assert release_resp.json()["release_reason"] == "telemetry discontinued"
    assert db_session.get(Equipment, monitor.equipment_id).status == "AVAILABLE"

    # Re-assign monitor so discharge tests releasing multiple active equipment items
    re_assign = client.post(
        f"/equipment/{monitor.equipment_id}/assign",
        json={"encounter_id": encounter_id},
        headers=nurse_headers,
    )
    assert re_assign.status_code == 200

    # 4. Doctor transfers patient to another compatible ICU isolation bed
    bed_2 = _pick_compatible_bed(db_session, bed_type="ICU", isolation=True, exclude={bed_1_id})
    transfer_resp = client.post(
        "/patients/WF0001/transfer",
        json={"destination_bed_id": bed_2.bed_id, "release_reason": "isolation unit move"},
    )
    assert transfer_resp.status_code == 200, transfer_resp.text
    assert transfer_resp.json() == {
        "patient_id": "WF0001",
        "encounter_id": encounter_id,
        "from_bed_id": bed_1_id,
        "to_bed_id": bed_2.bed_id,
        "status": "TRANSFERRED",
    }

    db_session.expire_all()
    assert db_session.get(Bed, bed_1_id).status == "CLEANING"
    assert db_session.get(Bed, bed_2.bed_id).status == "OCCUPIED"
    listed_beds = {bed["bed_id"]: bed for bed in client.get("/beds").json()["beds"]}
    assert listed_beds[bed_1_id]["patient_id"] is None
    assert listed_beds[bed_2.bed_id]["patient_id"] == "WF0001"

    history = (
        db_session.query(BedAssignment)
        .filter_by(encounter_id=encounter_id)
        .order_by(BedAssignment.assignment_id)
        .all()
    )
    assert len(history) == 2
    assert history[0].bed_id == bed_1_id and history[0].released_at is not None
    assert history[0].release_reason == "isolation unit move"
    assert history[1].bed_id == bed_2.bed_id and history[1].released_at is None

    # Bed 1 is in CLEANING and cannot be allocated until cleaning completes
    other_intake = client.post(
        "/patients/intake",
        json={
            "patient_id": "WF0002",
            "age_group": "51-65",
            "acuity": 5,
            "specialty": "Cardiology",
            "predicted_los": 2.0,
            "isolation_required": True,
            "ventilator_required": False,
        },
        headers=nurse_headers,
    )
    assert other_intake.status_code == 201
    blocked_approve = client.post(
        "/allocation/approve",
        json={"patient_id": "WF0002", "bed_id": bed_1_id},
    )
    assert blocked_approve.status_code == 409

    # Operator completes cleaning on bed 1 -> bed 1 becomes AVAILABLE
    clean_resp = client.post(f"/beds/{bed_1_id}/cleaning-complete", headers=operator_headers)
    assert clean_resp.status_code == 200, clean_resp.text
    assert clean_resp.json() == {"bed_id": bed_1_id, "status": "AVAILABLE"}
    assert db_session.get(Bed, bed_1_id).status == "AVAILABLE"

    # Now WF0002 can be admitted to bed 1
    ok_approve = client.post(
        "/allocation/approve",
        json={"patient_id": "WF0002", "bed_id": bed_1_id},
    )
    assert ok_approve.status_code == 200

    # 5. Doctor discharges WF0001 -> releases bed + equipment, bed enters CLEANING, patient stays DISCHARGED
    discharge_resp = client.post("/patients/WF0001/discharge")
    assert discharge_resp.status_code == 200, discharge_resp.text
    discharge_body = discharge_resp.json()
    assert discharge_body["patient_id"] == "WF0001"
    assert discharge_body["encounter_id"] == encounter_id
    assert discharge_body["bed_id"] == bed_2.bed_id
    assert discharge_body["bed_status"] == "CLEANING"
    assert set(discharge_body["released_equipment_ids"]) == {vent_id, monitor.equipment_id}
    assert discharge_body["patient_status"] == "DISCHARGED"
    assert discharge_body["encounter_status"] == "DISCHARGED"

    listed_beds = {bed["bed_id"]: bed for bed in client.get("/beds").json()["beds"]}
    assert listed_beds[bed_1_id]["patient_id"] == "WF0002"
    assert listed_beds[bed_2.bed_id]["patient_id"] is None

    db_session.expire_all()
    assert db_session.get(Bed, bed_2.bed_id).status == "CLEANING"
    assert db_session.get(Equipment, vent_id).status == "AVAILABLE"
    assert db_session.get(Equipment, monitor.equipment_id).status == "AVAILABLE"
    assert db_session.get(Patient, "WF0001").current_status == "DISCHARGED"
    assert db_session.query(BedAssignment).filter_by(encounter_id=encounter_id, released_at=None).count() == 0
    assert db_session.query(EquipmentAssignment).filter_by(encounter_id=encounter_id, released_at=None).count() == 0

    # 6. Discharged patient cannot re-enter the waiting queue or be allocated
    state = build_hospital_state(db_session)
    assert "WF0001" not in state.waiting_queue
    assert client.post("/allocation/recommend", json={"patient_id": "WF0001"}).status_code == 409
    assert client.post("/allocation/approve", json={"patient_id": "WF0001", "bed_id": bed_1_id}).status_code == 409
    assert client.post("/allocation/reject", json={"patient_id": "WF0001", "reason": "Not waiting"}).status_code == 409
    assert client.post("/patients/WF0001/discharge").status_code == 409


def test_legacy_waiting_patient_admission_creates_encounter_and_history_and_rolls_back_on_error(client, db_session):
    """Approving a seeded WAITING patient creates an Encounter + BedAssignment, and rolls back cleanly on error."""
    patient = (
        db_session.query(Patient)
        .filter(
            Patient.current_status == "WAITING",
            Patient.acuity == 5,
            Patient.ventilator_required.is_(False),
            Patient.isolation_required.is_(False),
        )
        .first()
    )
    assert patient is not None
    # Simulate a legacy pre-Milestone 2C WAITING patient without an Encounter row
    db_session.query(Encounter).filter_by(patient_id=patient.patient_id).delete()
    db_session.commit()
    assert db_session.query(Encounter).filter_by(patient_id=patient.patient_id).count() == 0

    # Incompatible WARD bed must fail AND roll back any encounter creation
    ward_bed = _pick_compatible_bed(db_session, bed_type="WARD")
    bad_resp = client.post(
        "/allocation/approve",
        json={"patient_id": patient.patient_id, "bed_id": ward_bed.bed_id},
    )
    assert bad_resp.status_code == 400
    assert db_session.query(Encounter).filter_by(patient_id=patient.patient_id).count() == 0
    assert db_session.query(BedAssignment).count() == 0

    # Compatible ICU bed succeeds and creates both Encounter and BedAssignment
    icu_bed = _pick_compatible_bed(db_session, bed_type="ICU")
    good_resp = client.post(
        "/allocation/approve",
        json={"patient_id": patient.patient_id, "bed_id": icu_bed.bed_id},
    )
    assert good_resp.status_code == 200
    encounters = db_session.query(Encounter).filter_by(patient_id=patient.patient_id).all()
    assert len(encounters) == 1
    assert encounters[0].status == "ADMITTED"
    assignments = db_session.query(BedAssignment).filter_by(encounter_id=encounters[0].encounter_id).all()
    assert len(assignments) == 1
    assert assignments[0].bed_id == icu_bed.bed_id


def test_intake_auto_generates_patient_id_and_supports_encounter_scoped_routes(client, db_session):
    intake_resp = client.post(
        "/patients/intake",
        json={
            "age_group": "18-35",
            "acuity": 2,
            "specialty": "General",
            "predicted_los": 1.5,
        },
    )
    assert intake_resp.status_code == 201, intake_resp.text
    body = intake_resp.json()
    pid = body["patient_id"]
    eid = body["encounter_id"]
    assert pid.startswith("P")
    assert len(pid) <= 10

    bed_1 = _pick_compatible_bed(db_session, bed_type="WARD")
    bed_2 = _pick_compatible_bed(db_session, bed_type="WARD", exclude={bed_1.bed_id})

    approve_resp = client.post(
        "/allocation/approve",
        json={"patient_id": pid, "bed_id": bed_1.bed_id, "encounter_id": eid},
    )
    assert approve_resp.status_code == 200

    transfer_resp = client.post(
        f"/encounters/{eid}/transfer",
        json={"destination_bed_id": bed_2.bed_id},
    )
    assert transfer_resp.status_code == 200
    assert transfer_resp.json()["to_bed_id"] == bed_2.bed_id

    discharge_resp = client.post(f"/encounters/{eid}/discharge")
    assert discharge_resp.status_code == 200
    assert discharge_resp.json()["encounter_status"] == "DISCHARGED"
    assert discharge_resp.json()["patient_status"] == "DISCHARGED"


def test_role_permissions_enforced_for_all_operational_endpoints(unauthenticated_client, client, admin_client, db_session):
    """Verify 401 unauthenticated and 403 role enforcement across every operational route."""
    _, nurse_headers = _auth_headers(db_session, username="perm_nurse", role="nurse")
    _, operator_headers = _auth_headers(db_session, username="perm_operator", role="operator")

    # Seed a patient, encounter, bed, and equipment item
    intake_payload = {
        "patient_id": "PERM01",
        "age_group": "36-50",
        "acuity": 2,
        "specialty": "General",
        "predicted_los": 2.0,
    }

    # Unauthenticated requests -> 401
    assert unauthenticated_client.post("/patients/intake", json=intake_payload).status_code == 401
    assert unauthenticated_client.post("/patients/PERM01/discharge").status_code == 401
    assert unauthenticated_client.post("/encounters/1/discharge").status_code == 401
    assert unauthenticated_client.post("/patients/PERM01/transfer", json={"destination_bed_id": "B001"}).status_code == 401
    assert unauthenticated_client.post("/encounters/1/transfer", json={"destination_bed_id": "B001"}).status_code == 401
    assert unauthenticated_client.post("/beds/B001/cleaning-complete").status_code == 401
    assert unauthenticated_client.post("/equipment/E001/assign", json={"patient_id": "PERM01"}).status_code == 401
    assert unauthenticated_client.post("/equipment/E001/release").status_code == 401

    # Operator cannot perform clinical intake, approve, discharge, transfer, or equipment assign/release
    assert unauthenticated_client.post("/patients/intake", json=intake_payload, headers=operator_headers).status_code == 403
    assert unauthenticated_client.post("/allocation/approve", json={"patient_id": "PERM01", "bed_id": "B001"}, headers=operator_headers).status_code == 403
    assert unauthenticated_client.post("/patients/PERM01/discharge", headers=operator_headers).status_code == 403
    assert unauthenticated_client.post("/encounters/1/discharge", headers=operator_headers).status_code == 403
    assert unauthenticated_client.post("/patients/PERM01/transfer", json={"destination_bed_id": "B001"}, headers=operator_headers).status_code == 403
    assert unauthenticated_client.post("/encounters/1/transfer", json={"destination_bed_id": "B001"}, headers=operator_headers).status_code == 403
    assert unauthenticated_client.post("/equipment/E001/assign", json={"patient_id": "PERM01"}, headers=operator_headers).status_code == 403
    assert unauthenticated_client.post("/equipment/E001/release", headers=operator_headers).status_code == 403

    # Nurse can intake, clean beds, assign/release equipment; cannot approve, transfer, or discharge
    nurse_intake = unauthenticated_client.post("/patients/intake", json=intake_payload, headers=nurse_headers)
    assert nurse_intake.status_code == 201
    eid = nurse_intake.json()["encounter_id"]
    ward_bed = _pick_compatible_bed(db_session, bed_type="WARD")
    ward_bed_2 = _pick_compatible_bed(db_session, bed_type="WARD", exclude={ward_bed.bed_id})

    assert unauthenticated_client.post("/allocation/approve", json={"patient_id": "PERM01", "bed_id": ward_bed.bed_id}, headers=nurse_headers).status_code == 403
    assert unauthenticated_client.post("/patients/PERM01/transfer", json={"destination_bed_id": ward_bed_2.bed_id}, headers=nurse_headers).status_code == 403
    assert unauthenticated_client.post(f"/encounters/{eid}/transfer", json={"destination_bed_id": ward_bed_2.bed_id}, headers=nurse_headers).status_code == 403
    assert unauthenticated_client.post("/patients/PERM01/discharge", headers=nurse_headers).status_code == 403
    assert unauthenticated_client.post(f"/encounters/{eid}/discharge", headers=nurse_headers).status_code == 403

    # Doctor (client) cannot mark bed cleaning complete (beds:clean is admin/nurse/operator)
    assert client.post("/allocation/approve", json={"patient_id": "PERM01", "bed_id": ward_bed.bed_id}).status_code == 200
    assert client.post(f"/patients/PERM01/transfer", json={"destination_bed_id": ward_bed_2.bed_id}).status_code == 200
    assert client.post(f"/beds/{ward_bed.bed_id}/cleaning-complete").status_code == 403

    # Nurse can complete cleaning
    assert unauthenticated_client.post(f"/beds/{ward_bed.bed_id}/cleaning-complete", headers=nurse_headers).status_code == 200

    # Admin can perform all operations (including discharge & cleaning)
    assert admin_client.post(f"/encounters/{eid}/discharge").status_code == 200
    assert admin_client.post(f"/beds/{ward_bed_2.bed_id}/cleaning-complete").status_code == 200
