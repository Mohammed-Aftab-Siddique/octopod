from conftest import login_headers


def test_unauthenticated_requests_are_rejected(client, seeded):
    assert client.get("/api/v1/employees").status_code == 401
    assert client.get("/api/v1/rosters?year=2026&month=11").status_code == 401


def test_employee_cannot_use_admin_endpoints(client, seeded):
    headers = login_headers(client, "E001", "Employee123!")
    assert client.get("/api/v1/employees").status_code == 403
    response = client.post(
        "/api/v1/employees",
        headers=headers,
        json={"employee_code": "X1", "full_name": "X", "email": "x@test.local"},
    )
    assert response.status_code == 403


def test_admin_login_and_role(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["role"] == "admin"
    assert me.json()["csrf_token"]
    employees = client.get("/api/v1/employees")
    assert employees.status_code == 200
    assert len(employees.json()) == 6
    assert "X-CSRF-Token" in headers


def test_csrf_is_required_for_mutations(client, seeded):
    login_headers(client, "admin@test.local", "Admin123!")
    response = client.post(
        "/api/v1/employees",
        json={"employee_code": "NEW1", "full_name": "New Person", "email": "new@test.local"},
    )
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_employee_lookup_returns_only_public_fields(client, seeded):
    response = client.get("/api/v1/employees/lookup", params={"employee_code": "e001"})
    assert response.status_code == 200
    assert response.json() == {"employee_code": "E001", "full_name": "Employee 1"}

    assert (
        client.get("/api/v1/employees/lookup", params={"employee_code": "nope"}).status_code == 404
    )


def test_roster_settings_are_admin_only(client, seeded):
    login_headers(client, "E001", "Employee123!")
    assert client.get("/api/v1/reference/roster-settings").status_code == 403

    login_headers(client, "admin@test.local", "Admin123!")
    assert client.get("/api/v1/reference/roster-settings").status_code == 200
    missing_csrf = client.put(
        "/api/v1/reference/roster-settings",
        json={"consecutive_off_days": 2},
    )
    assert missing_csrf.status_code == 403
    assert "CSRF" in missing_csrf.json()["detail"]


def test_login_by_employee_code(client, seeded):
    response = client.post(
        "/api/v1/auth/login", json={"identifier": "E002", "password": "Employee123!"}
    )
    assert response.status_code == 200
    user = response.json()["user"]
    assert user["role"] == "employee"
    assert user["employee_code"] == "E002"

    assert (
        client.post(
            "/api/v1/auth/login", json={"identifier": "E002", "password": "wrong-password"}
        ).status_code
        == 401
    )


def test_logout_invalidates_session(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_password_reset_revokes_existing_sessions(client, seeded):
    login_headers(client, "E001", "Employee123!")
    assert client.get("/api/v1/auth/me").status_code == 200
    employee_cookie = client.cookies.get("octopod_session")
    employee_id = seeded["employees"][0][0]

    admin_headers = login_headers(client, "admin@test.local", "Admin123!")
    reset = client.post(
        f"/api/v1/employees/{employee_id}/reset-password",
        headers=admin_headers,
        json={"password": "NewPassword123!"},
    )
    assert reset.status_code == 204

    client.cookies.set("octopod_session", employee_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401

    assert (
        client.post(
            "/api/v1/auth/login",
            json={"identifier": "E001", "password": "NewPassword123!"},
        ).status_code
        == 200
    )


def test_deactivation_revokes_existing_sessions(client, seeded):
    login_headers(client, "E001", "Employee123!")
    employee_cookie = client.cookies.get("octopod_session")
    employee_id = seeded["employees"][0][0]

    admin_headers = login_headers(client, "admin@test.local", "Admin123!")
    assert (
        client.post(
            f"/api/v1/employees/{employee_id}/deactivate", headers=admin_headers
        ).status_code
        == 200
    )

    client.cookies.set("octopod_session", employee_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401
