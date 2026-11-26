from backend.models import AuditLog, Bed, Patient
from simulator.hospital.allocation_rules import candidate_bed_types


def test_root_response_shape(unauthenticated_client):
    response = unauthenticated_client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "CareGrid API is running"}


def test_patient_bed_staff_and_equipment_list_envelopes(admin_client):
    expected = {
        "/patients": ("patients", {
            "patient_id", "age_group", "acuity", "specialty", "predicted_los",
            "isolation_required", "ventilator_required", "arrival_time", "current_status",
        }),
        "/beds": ("beds", {
            "bed_id", "bed_type", "ward", "status", "isolation_capable",
        }),
        "/staff": ("staff", {
            "staff_id", "role", "skill_level", "shift", "workload",
        }),
        "/equipment": ("equipment", {"equipment_id", "type", "status", "location"}),
    }

    for path, (envelope, item_fields) in expected.items():
        response = admin_client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {envelope}
        assert body[envelope]
        assert set(body[envelope][0]) == item_fields


def test_recommendation_response_preserves_null_bed_id(client, db_session):
    patient = db_session.query(Patient).filter(
        Patient.current_status == "WAITING"
    ).first()
    assert patient is not None
    db_session.query(Bed).update({Bed.status: "OCCUPIED"})
    db_session.commit()

    response = client.post(
        "/allocation/recommend", json={"patient_id": patient.patient_id}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "patient_id", "recommended_bed_id", "algorithm", "reason", "status",
    }
    assert body["recommended_bed_id"] is None
    assert body["status"] == "NO_SUITABLE_BED"


def test_allocation_approval_response_shape(client, db_session):
    patient = db_session.query(Patient).filter(
        Patient.current_status == "WAITING"
    ).order_by(Patient.patient_id).first()
    assert patient is not None
    compatible_types = candidate_bed_types(patient.acuity)
    bed_query = db_session.query(Bed).filter(
        Bed.status == "AVAILABLE",
        Bed.bed_type.in_(compatible_types),
    )
    if patient.isolation_required:
        bed_query = bed_query.filter(Bed.isolation_capable.is_(True))
    bed = bed_query.order_by(Bed.bed_id).first()
    assert bed is not None

    response = client.post(
        "/allocation/approve",
        json={"patient_id": patient.patient_id, "bed_id": bed.bed_id},
    )

    assert response.status_code == 200
    assert response.json() == {
        "patient_id": patient.patient_id,
        "bed_id": bed.bed_id,
        "status": "APPROVED",
    }


def test_surge_response_has_nested_metrics(admin_client):
    response = admin_client.post(
        "/surge/simulate",
        json={"arrival_rate_multiplier": 1.0, "duration_hours": 1},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "status", "arrival_rate_multiplier", "duration_hours", "patients_arrived",
        "simulation_start", "simulation_end", "metrics",
    }
    assert body["status"] == "COMPLETED"
    metrics = body["metrics"]
    assert set(metrics) == {
        "patients_total", "patients_admitted", "patients_discharged",
        "patients_still_waiting", "avg_wait_min", "median_wait_min",
        "avg_wait_incl_unadmitted_min", "p90_wait_incl_unadmitted_min",
        "p90_wait_min", "max_wait_min", "avg_wait_by_acuity_min",
        "pct_admitted_within_60min", "icu_utilization", "step_down_utilization",
        "ward_utilization", "overall_bed_utilization", "ventilator_utilization",
        "bed_turnover_per_bed_per_day", "peak_waiting_queue", "constraint_violations",
        "measurement_window_hours", "waiting_patients_elapsed_wait_min",
    }
    assert set(metrics["waiting_patients_elapsed_wait_min"]) == {"avg", "max"}
    assert set(metrics["avg_wait_by_acuity_min"]) == {"1", "2", "3", "4", "5"}
    assert set(metrics["constraint_violations"]) == {
        "acuity_tier", "isolation", "ventilator", "double_booking", "total",
    }


def test_metrics_response_shape(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    assert set(response.json()) == {
        "patients_total", "patients_waiting", "patients_admitted", "beds_total",
        "beds_available", "beds_occupied", "bed_occupancy_rate", "ventilators_total",
        "ventilators_available", "ventilators_in_use", "approved_allocations",
    }


def test_audit_response_preserves_nullable_bed_id(admin_client, db_session):
    patient = db_session.query(Patient).first()
    db_session.add(AuditLog(
        patient_id=patient.patient_id,
        bed_id=None,
        action="TEST_EVENT",
        algorithm="rule_based",
    ))
    db_session.commit()

    response = admin_client.get("/audit")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"audit"}
    event = next(item for item in body["audit"] if item["action"] == "TEST_EVENT")
    assert set(event) == {"patient_id", "bed_id", "action", "algorithm", "timestamp"}
    assert event["bed_id"] is None
