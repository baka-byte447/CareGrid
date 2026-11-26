from backend.models import Encounter, FhirResource, Patient, TelemetryRecord


def encounter(status="arrived"):
    return {"resourceType": "Encounter", "id": "visit", "class": {"code": "IMP"},
            "status": status, "subject": {"reference": "Patient/incoming"}}


def bundle(*resources):
    return {"resourceType": "Bundle", "type": "transaction", "entry": [
        {"resource": r, "request": {"method": "PUT", "url": f"{r['resourceType']}/{r['id']}"}}
        for r in resources]}


def test_transaction_and_encounter_replay(client, db_session):
    condition = {"resourceType": "Condition", "id": "triage", "subject": {"reference": "Patient/incoming"},
                 "severity": {"coding": [{"system": "urn:caregrid:acuity", "code": "2"}]}}
    data = bundle(encounter(), condition, {"resourceType": "Patient", "id": "incoming"})
    assert client.post("/fhir/Bundle", json=data).status_code == 201
    assert client.post("/fhir/Encounter", json=encounter()).status_code == 201
    assert db_session.query(Encounter).filter_by(patient_id="incoming").count() == 1
    assert db_session.get(Patient, "incoming").acuity == 2


def test_invalid_bundle_rolls_back(client, db_session):
    data = bundle({"resourceType": "Device", "id": "new", "status": "active"}, encounter())
    response = client.post("/fhir/Bundle", json=data)
    assert response.status_code == 422
    assert response.json()["resourceType"] == "OperationOutcome"
    assert db_session.get(FhirResource, "Device/new") is None
    assert client.post("/fhir/Encounter", content="{").json()["resourceType"] == "OperationOutcome"


def test_telemetry_records_request_without_releasing_bed(client, db_session):
    from backend.models import Bed
    from backend.services.patient_lifecycle import approve_encounter
    p = db_session.query(Patient).filter_by(current_status="WAITING", acuity=2).first()
    enc = db_session.query(Encounter).filter_by(patient_id=p.patient_id, status="WAITING").one()
    bed = db_session.query(Bed).filter_by(bed_type="WARD", isolation_capable=True).first()
    approve_encounter(db_session, enc.encounter_id, bed.bed_id)
    db_session.commit()
    result = client.post(f"/patients/{p.patient_id}/telemetry", json=dict(
        respiratory_rate=26, spo2=90, systolic_bp=100, pulse=110, temperature=37,
        consciousness="Alert", supplemental_oxygen=False))
    assert result.status_code == 201
    assert result.json()["transfer_requested"]
    assert db_session.query(TelemetryRecord).one().score == 9
    assert p.acuity == enc.acuity == 5
    assert bed.status == "OCCUPIED"


def test_r4_invalid_nested_field(client):
    data = encounter()
    data["participant"] = [{"individual": 5}]
    response = client.post("/fhir/Encounter", json=data)
    assert response.status_code == 422
    assert response.json()["resourceType"] == "OperationOutcome"


def test_adaptive_surge_route(admin_client):
    response = admin_client.post("/surge/simulate", json={"adaptive": True, "arrival_rate_multiplier": 3,
                                                           "duration_hours": 12})
    assert response.status_code == 200, response.text
    operations = response.json()["operations"]
    assert 0 <= operations["fatigue"] <= 1
    assert 0 <= operations["overtime_minutes"] <= 300


def test_drawer_explanation_matches_saved_decision(client, db_session):
    from backend.models import AllocationRecommendation
    patient = db_session.query(Patient).filter_by(current_status="WAITING").first()
    data = client.post("/allocation/recommend", json={"patient_id": patient.patient_id,
                                                      "algorithm": "dqn_safe"}).json()
    assert data["explanation"]["counterfactual"]
    assert db_session.get(AllocationRecommendation, data["recommendation_id"]).explanation == data["explanation"]


def test_fhir_admission_transfer_and_discharge(client, db_session):
    from backend.models import Bed, BedAssignment, Equipment
    patient = {"resourceType": "Patient", "id": "incoming", "birthDate": "1984-02-10"}
    condition = {"resourceType": "Condition", "id": "severity", "subject": {"reference": "urn:uuid:patient"},
                 "severity": {"coding": [{"system": "urn:caregrid:acuity", "code": "2"}]}}
    device = {"resourceType": "Device", "id": "pump", "type": {"text": "pump"}, "status": "active"}
    wards = db_session.query(Bed).filter_by(bed_type="WARD").limit(2).all()
    visit = encounter("in-progress")
    visit["subject"]["reference"] = "urn:uuid:patient"
    visit["location"] = [{"location": {"reference": "Location/" + wards[0].bed_id}}]
    data = bundle(visit, condition, device, patient)
    data["entry"][-1]["fullUrl"] = "urn:uuid:patient"
    response = client.post("/fhir/Bundle", json=data)
    assert response.status_code == 201, response.text
    assert db_session.get(Equipment, "pump").type == "PUMP"
    visit["subject"]["reference"] = "Patient/incoming"
    visit["location"][0]["location"]["reference"] = "Location/" + wards[1].bed_id
    assert client.post("/fhir/Encounter", json=visit).status_code == 201
    visit["status"] = "finished"
    assert client.post("/fhir/Encounter", json=visit).status_code == 201
    enc = db_session.query(Encounter).filter_by(patient_id="incoming").one()
    assignments = db_session.query(BedAssignment).filter_by(encounter_id=enc.encounter_id).all()
    assert enc.status == "DISCHARGED"
    assert len(assignments) == 2 and all(a.released_at for a in assignments)
