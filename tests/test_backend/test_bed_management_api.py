from backend.models import AuditLog, Bed


def test_admin_creates_bed_available_with_unassociated_audit(admin_client, db_session):
    response = admin_client.post("/beds", json={
        "bed_id": "BED-NEW", "bed_type": "ICU", "ward": "ICU-A",
        "isolation_capable": True,
    })
    assert response.status_code == 201
    assert response.json() == {
        "message": "Bed created successfully",
        "bed": {"bed_id": "BED-NEW", "bed_type": "ICU", "ward": "ICU-A",
                "status": "AVAILABLE", "isolation_capable": True},
    }
    audit = db_session.query(AuditLog).filter_by(bed_id="BED-NEW", action="BED_CREATED").one()
    assert audit.patient_id is None


def test_duplicate_bed_id_conflicts(admin_client):
    payload = {"bed_id": "BED-NEW", "bed_type": "ICU", "ward": "ICU-A"}
    assert admin_client.post("/beds", json=payload).status_code == 201
    assert admin_client.post("/beds", json=payload).status_code == 409


def test_bed_creation_requires_admin(client):
    response = client.post("/beds", json={"bed_id": "BED-NEW", "bed_type": "ICU", "ward": "ICU-A"})
    assert response.status_code == 403


def test_bed_creation_rejects_client_status(admin_client):
    response = admin_client.post("/beds", json={
        "bed_id": "BED-NEW", "bed_type": "ICU", "ward": "ICU-A", "status": "OCCUPIED",
    })
    assert response.status_code == 422


def test_bed_creation_rejects_missing_fields(admin_client):
    assert admin_client.post("/beds", json={"bed_id": "BED-NEW"}).status_code == 422


def test_bed_creation_requires_auth(unauthenticated_client):
    response = unauthenticated_client.post("/beds", json={"bed_id": "BED-NEW", "bed_type": "ICU", "ward": "ICU-A"})
    assert response.status_code == 401


def test_empty_bed_requires_assignment_and_lifecycle_release(client, db_session):
    bed = db_session.query(Bed).first()
    bed.status = "OCCUPIED"
    db_session.commit()
    response = client.post(f"/beds/{bed.bed_id}/empty")
    assert response.status_code == 409


def test_empty_bed_conflicts_for_available_and_cleaning_states(client, db_session):
    bed = db_session.query(Bed).first()
    assert client.post(f"/beds/{bed.bed_id}/empty").status_code == 409
    bed.status = "CLEANING"
    db_session.commit()
    response = client.post(f"/beds/{bed.bed_id}/empty")
    assert response.status_code == 409
    assert "already awaiting cleaning" in response.json()["detail"]


def test_audit_failure_rolls_back_bed_creation(admin_client, db_session, monkeypatch):
    from sqlalchemy import event

    def fail_audit_insert(mapper, connection, target):
        raise RuntimeError("simulated audit failure")

    event.listen(AuditLog, "before_insert", fail_audit_insert)
    try:
        response = admin_client.post("/beds", json={
            "bed_id": "BED-ROLL", "bed_type": "ICU", "ward": "ICU-A",
        })
    finally:
        event.remove(AuditLog, "before_insert", fail_audit_insert)
    assert response.status_code == 500
    assert db_session.get(Bed, "BED-ROLL") is None


def test_empty_bed_not_found(client):
    assert client.post("/beds/MISSING/empty").status_code == 404


def test_empty_bed_requires_auth(unauthenticated_client):
    assert unauthenticated_client.post("/beds/MISSING/empty").status_code == 401
