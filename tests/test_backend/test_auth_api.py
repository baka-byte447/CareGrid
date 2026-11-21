from backend.models import User
from backend.auth.security import create_access_token, hash_password, decode_access_token


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
    assert "password" not in response.json()
    assert "hashed_password" not in response.json()


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


def test_login_successful(unauthenticated_client, db_session):
    user = User(
        username="login_test_user",
        email="login_test@example.com",
        hashed_password=hash_password("ValidPassword123!"),
        role="nurse",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    response = unauthenticated_client.post(
        "/auth/login",
        json={"username": "login_test_user", "password": "ValidPassword123!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    payload = decode_access_token(data["access_token"])
    assert payload is not None
    assert payload.get("sub") == str(user.id)
    assert payload.get("role") == "nurse"


def test_login_invalid_password_rejected(unauthenticated_client, db_session):
    user = User(
        username="wrong_pass_user",
        email="wrong_pass@example.com",
        hashed_password=hash_password("CorrectPass123!"),
        role="doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    response = unauthenticated_client.post(
        "/auth/login",
        json={"username": "wrong_pass_user", "password": "IncorrectPassword123!"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_nonexistent_user_rejected(unauthenticated_client):
    response = unauthenticated_client.post(
        "/auth/login",
        json={"username": "ghost_user", "password": "SomePassword123!"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_inactive_user_rejected(unauthenticated_client, db_session):
    user = User(
        username="inactive_user",
        email="inactive@example.com",
        hashed_password=hash_password("InactivePass123!"),
        role="operator",
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()

    # Inactive user with correct credentials must be rejected with 403
    response = unauthenticated_client.post(
        "/auth/login",
        json={"username": "inactive_user", "password": "InactivePass123!"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Account is inactive"

    # Inactive user with wrong credentials returns 401 (no status leakage)
    bad_pass_response = unauthenticated_client.post(
        "/auth/login",
        json={"username": "inactive_user", "password": "WrongPassword!"},
    )
    assert bad_pass_response.status_code == 401


def test_get_me_with_valid_token(client):
    # client fixture is pre-authenticated as test_doctor
    response = client.get("/auth/me")

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "test_doctor"
    assert data["role"] == "doctor"
    assert data["is_active"] is True
    assert "password" not in data
    assert "hashed_password" not in data


def test_get_me_without_token_rejected(unauthenticated_client):
    response = unauthenticated_client.get("/auth/me")
    assert response.status_code == 401

    invalid_response = unauthenticated_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert invalid_response.status_code == 401


def test_public_registration_unavailable(unauthenticated_client):
    response = unauthenticated_client.post(
        "/auth/register",
        json={
            "username": "random_applicant",
            "email": "applicant@example.com",
            "password": "ApplicantPass123!",
        },
    )

    # Public registration is disabled; route must not be registered or exposed
    assert response.status_code == 404


def test_admin_list_users(admin_client, db_session):
    response = admin_client.get("/auth/users")

    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)
    assert len(users) >= 1

    for u in users:
        assert "id" in u
        assert "username" in u
        assert "email" in u
        assert "role" in u
        assert "is_active" in u
        assert "password" not in u
        assert "hashed_password" not in u


def test_admin_update_user_role_and_status(admin_client, db_session):
    target = User(
        username="modifiable_user",
        email="modifiable@example.com",
        hashed_password=hash_password("Pass123456!"),
        role="nurse",
        is_active=True,
    )
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)

    # Admin updates another user's role and status
    response = admin_client.patch(
        f"/auth/users/{target.id}",
        json={"role": "operator", "is_active": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "operator"
    assert data["is_active"] is False

    db_session.refresh(target)
    assert target.role == "operator"
    assert target.is_active is False


def test_admin_cannot_deactivate_own_account(admin_client):
    me_resp = admin_client.get("/auth/me")
    assert me_resp.status_code == 200
    admin_id = me_resp.json()["id"]

    response = admin_client.patch(
        f"/auth/users/{admin_id}",
        json={"is_active": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot deactivate your own account"


def test_admin_cannot_remove_own_admin_role(admin_client):
    me_resp = admin_client.get("/auth/me")
    assert me_resp.status_code == 200
    admin_id = me_resp.json()["id"]

    response = admin_client.patch(
        f"/auth/users/{admin_id}",
        json={"role": "doctor"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot remove your own admin role"


def test_non_admin_cannot_access_admin_endpoints(client, db_session):
    # client fixture is a Doctor
    list_resp = client.get("/auth/users")
    assert list_resp.status_code == 403

    create_resp = client.post(
        "/auth/users",
        json={
            "username": "unauthorized_create",
            "email": "unauth@example.com",
            "password": "Password123!",
            "role": "nurse",
        },
    )
    assert create_resp.status_code == 403

    patch_resp = client.patch(
        "/auth/users/1",
        json={"role": "operator"},
    )
    assert patch_resp.status_code == 403


def test_update_user_validation_errors(admin_client, db_session):
    # Non-existent user
    not_found_resp = admin_client.patch(
        "/auth/users/999999",
        json={"role": "doctor"},
    )
    assert not_found_resp.status_code == 404

    # Empty payload
    target = User(
        username="empty_update_user",
        email="empty_update@example.com",
        hashed_password="test-hash",
        role="nurse",
        is_active=True,
    )
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)

    empty_resp = admin_client.patch(
        f"/auth/users/{target.id}",
        json={},
    )
    assert empty_resp.status_code == 400
    assert empty_resp.json()["detail"] == "No update fields provided"

    # Invalid role
    invalid_role_resp = admin_client.patch(
        f"/auth/users/{target.id}",
        json={"role": "god_mode"},
    )
    assert invalid_role_resp.status_code == 400
    assert invalid_role_resp.json()["detail"] == "Invalid role"

    # Null is_active
    null_active_resp = admin_client.patch(
        f"/auth/users/{target.id}",
        json={"is_active": None},
    )
    assert null_active_resp.status_code == 400
    assert null_active_resp.json()["detail"] == "is_active cannot be null"


def test_inactive_user_token_rejected_on_protected_endpoints(unauthenticated_client, db_session):
    inactive = User(
        username="deactivated_nurse",
        email="deactivated@example.com",
        hashed_password=hash_password("Pass12345!"),
        role="nurse",
        is_active=False,
    )
    db_session.add(inactive)
    db_session.commit()
    db_session.refresh(inactive)

    token = create_access_token(
        data={"sub": str(inactive.id), "role": inactive.role}
    )

    response = unauthenticated_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401

    patients_response = unauthenticated_client.get(
        "/patients",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patients_response.status_code == 401
