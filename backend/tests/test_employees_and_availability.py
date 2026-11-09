from conftest import login_headers


def test_employee_crud_and_unique_code(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    payload = {"employee_code": "EMP900", "full_name": "New Hire", "email": "hire@example.com"}
    response = client.post("/api/v1/employees", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    employee = response.json()
    assert employee["employee_code"] == "EMP900"

    duplicate = client.post(
        "/api/v1/employees", headers=headers, json={**payload, "email": "other@example.com"}
    )
    assert duplicate.status_code == 409

    updated = client.patch(
        f"/api/v1/employees/{employee['id']}",
        headers=headers,
        json={"full_name": "Renamed Hire"},
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Renamed Hire"

    deactivated = client.post(f"/api/v1/employees/{employee['id']}/deactivate", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    lookup = client.get("/api/v1/employees/lookup", params={"employee_code": "EMP900"})
    assert lookup.status_code == 404

    login = client.post(
        "/api/v1/auth/login", json={"identifier": "EMP900", "password": "Employee123!"}
    )
    assert login.status_code == 401


def test_availability_range_create_list_delete(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    employee_id = seeded["employees"][0][0]

    response = client.post(
        f"/api/v1/employees/{employee_id}/availability",
        headers=headers,
        json={
            "start_date": "2026-11-10",
            "end_date": "2026-11-12",
            "kind": "leave",
            "note": "Approved",
        },
    )
    assert response.status_code == 201, response.text
    assert len(response.json()) == 3

    listing = client.get(
        f"/api/v1/employees/{employee_id}/availability",
        params={"from": "2026-11-01", "to": "2026-11-30"},
    )
    assert listing.status_code == 200
    entries = listing.json()
    assert [entry["kind"] for entry in entries] == ["leave", "leave", "leave"]

    # Re-submitting an overlapping range updates rather than duplicates.
    updated = client.post(
        f"/api/v1/employees/{employee_id}/availability",
        headers=headers,
        json={
            "start_date": "2026-11-11",
            "end_date": "2026-11-13",
            "kind": "comp_off",
        },
    )
    assert updated.status_code == 201
    listing = client.get(
        f"/api/v1/employees/{employee_id}/availability",
        params={"from": "2026-11-01", "to": "2026-11-30"},
    ).json()
    assert len(listing) == 4
    assert sum(1 for entry in listing if entry["kind"] == "comp_off") == 3

    deleted = client.delete(
        f"/api/v1/employees/{employee_id}/availability/{entries[0]['id']}", headers=headers
    )
    assert deleted.status_code == 204


def test_whitespace_only_input_is_rejected(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    blank = client.post(
        "/api/v1/employees",
        headers=headers,
        json={"employee_code": "   ", "full_name": "Valid Name", "email": "blank@example.com"},
    )
    assert blank.status_code == 422

    blank_name = client.post(
        "/api/v1/employees",
        headers=headers,
        json={"employee_code": "EMP777", "full_name": "   ", "email": "blank2@example.com"},
    )
    assert blank_name.status_code == 422

    blank_holiday = client.post(
        "/api/v1/reference/holidays",
        headers=headers,
        json={"date": "2026-11-20", "label": "   "},
    )
    assert blank_holiday.status_code == 422


def test_case_insensitive_duplicate_identifiers_are_rejected(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    payload = {"employee_code": "EMP901", "full_name": "Case Test", "email": "case@example.com"}
    assert client.post("/api/v1/employees", headers=headers, json=payload).status_code == 201

    duplicate_code = client.post(
        "/api/v1/employees",
        headers=headers,
        json={**payload, "employee_code": "emp901", "email": "case2@example.com"},
    )
    assert duplicate_code.status_code == 409

    duplicate_email = client.post(
        "/api/v1/employees",
        headers=headers,
        json={**payload, "employee_code": "EMP902", "email": "CASE@example.com"},
    )
    assert duplicate_email.status_code == 409


def test_availability_validation(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    employee_id = seeded["employees"][0][0]
    response = client.post(
        f"/api/v1/employees/{employee_id}/availability",
        headers=headers,
        json={"start_date": "2026-11-12", "end_date": "2026-11-10", "kind": "leave"},
    )
    assert response.status_code == 422
