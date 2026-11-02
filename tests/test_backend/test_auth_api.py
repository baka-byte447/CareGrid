from backend.models import User
from backend.auth.security import create_access_token


def test_unauthenticated_access_returns_401(client):
    response = client.get(
        "/patients",
        headers={"Authorization": ""}
    )

    assert response.status_code == 401


def test_invalid_token_returns_401(client):
    response = client.get(
        "/patients",
        headers={"Authorization": "Bearer invalid-token"}
    )

    assert response.status_code == 401


def test_nurse_cannot_recommend_allocation(client, db_session):
    # Create a real Nurse user in the test database
    nurse = User(
        username="test_nurse",
        email="test_nurse@example.com",
        hashed_password="test-hash",
        role="nurse",
        is_active=True,
    )

    db_session.add(nurse)
    db_session.commit()
    db_session.refresh(nurse)

    # Generate token using the Nurse's actual database ID
    token = create_access_token(
        data={"sub": str(nurse.id), "role": nurse.role}
    )

    response = client.post(
        "/allocation/recommend",
        json={"patient_id": "INVALID"},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_doctor_can_access_allocation_recommendation(client):
    response = client.post(
        "/allocation/recommend",
        json={"patient_id": "INVALID"}
    )

    # The Doctor is authenticated; the invalid patient should produce 404.
    assert response.status_code == 404

def test_admin_can_create_user(admin_client):
    response = admin_client.post(
        "/auth/users",
        json={
            "username": "new_doctor",
            "email": "new_doctor@example.com",
            "password": "DoctorPass123!",
            "role": "doctor",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "doctor"


def test_doctor_cannot_create_users(client, db_session):
    from backend.auth.security import create_access_token
    from backend.models import User

    doctor = User(
        username="restricted_doctor",
        email="restricted_doctor@example.com",
        hashed_password="test-hash",
        role="doctor",
        is_active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    token = create_access_token(
        data={"sub": str(doctor.id), "role": doctor.role}
    )

    response = client.post(
        "/auth/users",
        json={
            "username": "blocked_user",
            "email": "blocked@example.com",
            "password": "TestPass123!",
            "role": "nurse",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_invalid_role_is_rejected(admin_client):
    response = admin_client.post(
        "/auth/users",
        json={
            "username": "invalid_role_user",
            "email": "invalid_role@example.com",
            "password": "TestPass123!",
            "role": "superuser",
        },
    )

    assert response.status_code == 400


def test_duplicate_user_is_rejected(admin_client):
    # First creation should succeed
    first_response = admin_client.post(
        "/auth/users",
        json={
            "username": "duplicate_user",
            "email": "duplicate@example.com",
            "password": "TestPass123!",
            "role": "doctor",
        },
    )

    assert first_response.status_code == 201

    # Second creation with the same username should fail
    second_response = admin_client.post(
        "/auth/users",
        json={
            "username": "duplicate_user",
            "email": "another@example.com",
            "password": "TestPass123!",
            "role": "doctor",
        },
    )

    assert second_response.status_code == 409