from collections import Counter

from conftest import login_headers


def _set_requirements(client, headers, count_per_shift):
    requirements = [
        {"weekday": weekday, "status_code": code, "required_count": count_per_shift}
        for weekday in range(7)
        for code in ("G", "M", "A", "N")
    ]
    response = client.put(
        "/api/v1/reference/staffing-requirements",
        headers=headers,
        json={"requirements": requirements},
    )
    assert response.status_code == 200, response.text


def _create_roster(client, headers, year=2026, month=11):
    response = client.post("/api/v1/rosters", headers=headers, json={"year": year, "month": month})
    assert response.status_code in (200, 201), response.text
    return response.json()


def test_only_one_draft_exists_per_month(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    first = _create_roster(client, headers)
    second = _create_roster(client, headers)
    assert first["id"] == second["id"]
    assert first["version"] == second["version"] == 1

    from sqlalchemy import func, select

    from app.db.session import get_sessionmaker
    from app.models.roster import RosterPeriod, RosterStatus

    with get_sessionmaker()() as db:
        count = db.scalar(
            select(func.count(RosterPeriod.id)).where(
                RosterPeriod.year == 2026,
                RosterPeriod.month == 11,
                RosterPeriod.status == RosterStatus.draft,
            )
        )
        assert count == 1


def test_generation_respects_leave_and_has_no_conflicts(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    _set_requirements(client, headers, 1)
    roster = _create_roster(client, headers)
    employee_id = seeded["employees"][0][0]

    leave = client.post(
        f"/api/v1/employees/{employee_id}/availability",
        headers=headers,
        json={"start_date": "2026-11-10", "end_date": "2026-11-12", "kind": "leave"},
    )
    assert leave.status_code == 201

    response = client.post(f"/api/v1/rosters/{roster['id']}/generate", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    grid = result["roster"]
    assignments = grid["assignments"]

    expected = len(grid["employees"]) * len(grid["days"])
    assert len(assignments) == expected
    keys = [(item["employee_id"], item["date"]) for item in assignments]
    assert len(keys) == len(set(keys))

    leave_rows = [
        item
        for item in assignments
        if item["employee_id"] == employee_id
        and item["date"] in ("2026-11-10", "2026-11-11", "2026-11-12")
    ]
    assert {item["status_code"] for item in leave_rows} == {"L"}

    for day in grid["days"]:
        codes = [item["status_code"] for item in assignments if item["date"] == day["date"]]
        assert len(codes) == len(grid["employees"])
        assert all(code for code in codes)


def test_generation_reports_shortages(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    _set_requirements(client, headers, 3)  # 12 required per day, only 6 employees
    roster = _create_roster(client, headers)

    response = client.post(f"/api/v1/rosters/{roster['id']}/generate", headers=headers)
    assert response.status_code == 200
    shortages = response.json()["shortages"]
    assert shortages
    assert all(shortage["assigned"] < shortage["required"] for shortage in shortages)


def test_holidays_are_applied_to_everyone(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    _set_requirements(client, headers, 1)
    roster = _create_roster(client, headers)

    holiday = client.post(
        "/api/v1/reference/holidays",
        headers=headers,
        json={"date": "2026-11-15", "label": "Company Day"},
    )
    assert holiday.status_code == 201, holiday.text

    response = client.post(f"/api/v1/rosters/{roster['id']}/generate", headers=headers)
    assert response.status_code == 200
    grid = response.json()["roster"]
    holiday_codes = [
        item["status_code"] for item in grid["assignments"] if item["date"] == "2026-11-15"
    ]
    assert holiday_codes == ["H"] * len(grid["employees"])
    holiday_day = next(day for day in grid["days"] if day["date"] == "2026-11-15")
    assert holiday_day["holiday"] == "Company Day"


def test_editing_validation_and_publishing_flow(client, seeded):
    admin_headers = login_headers(client, "admin@test.local", "Admin123!")
    _set_requirements(client, headers=admin_headers, count_per_shift=1)
    roster = _create_roster(client, admin_headers)
    roster_id = roster["id"]
    employee_id = seeded["employees"][0][0]

    invalid = client.patch(
        f"/api/v1/rosters/{roster_id}/assignments",
        headers=admin_headers,
        json={
            "assignments": [
                {"employee_id": employee_id, "date": "2026-11-05", "status_code": "M"},
                {"employee_id": employee_id, "date": "2026-11-05", "status_code": "G"},
            ]
        },
    )
    assert invalid.status_code == 400

    outside = client.patch(
        f"/api/v1/rosters/{roster_id}/assignments",
        headers=admin_headers,
        json={
            "assignments": [{"employee_id": employee_id, "date": "2026-12-01", "status_code": "M"}]
        },
    )
    assert outside.status_code == 400

    updated = client.patch(
        f"/api/v1/rosters/{roster_id}/assignments",
        headers=admin_headers,
        json={
            "assignments": [{"employee_id": employee_id, "date": "2026-11-05", "status_code": "M"}]
        },
    )
    assert updated.status_code == 200
    assert any(
        item["employee_id"] == employee_id
        and item["date"] == "2026-11-05"
        and item["status_code"] == "M"
        for item in updated.json()["assignments"]
    )

    published = client.post(f"/api/v1/rosters/{roster_id}/publish", headers=admin_headers)
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    # Published rosters are immutable.
    locked = client.patch(
        f"/api/v1/rosters/{roster_id}/assignments",
        headers=admin_headers,
        json={
            "assignments": [
                {
                    "employee_id": employee_id,
                    "date": "2026-11-06",
                    "status_code": "G",
                }
            ]
        },
    )
    assert locked.status_code == 409

    # A new draft version does not replace the published roster until approved.
    new_draft = _create_roster(client, admin_headers)
    assert new_draft["id"] != roster_id
    assert new_draft["version"] == 2

    empty_publish = client.post(f"/api/v1/rosters/{new_draft['id']}/publish", headers=admin_headers)
    assert empty_publish.status_code == 400

    login_headers(client, "E001", "Employee123!")
    me = client.get("/api/v1/me/roster", params={"year": 2026, "month": 11})
    assert me.status_code == 200
    assert me.json()["status"] == "published"
    assert me.json()["id"] == roster_id

    forbidden = client.get(f"/api/v1/rosters/{roster_id}")
    assert forbidden.status_code == 403

    export = client.get(f"/api/v1/rosters/{roster_id}/export.png")
    assert export.status_code == 200
    assert export.headers["content-type"] == "image/png"
    assert export.content.startswith(b"\x89PNG")

    draft_export = client.get(f"/api/v1/rosters/{new_draft['id']}/export.png")
    assert draft_export.status_code == 403


def test_published_version_excludes_later_hires(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    _set_requirements(client, headers, 1)
    roster = _create_roster(client, headers)
    generated = client.post(f"/api/v1/rosters/{roster['id']}/generate", headers=headers)
    assert generated.status_code == 200
    published = client.post(f"/api/v1/rosters/{roster['id']}/publish", headers=headers)
    assert published.status_code == 200

    created = client.post(
        "/api/v1/employees",
        headers=headers,
        json={
            "employee_code": "LATE01",
            "full_name": "Late Hire",
            "email": "late@example.com",
        },
    )
    assert created.status_code == 201
    late_id = created.json()["id"]

    grid = client.get(f"/api/v1/rosters/{roster['id']}")
    assert grid.status_code == 200
    employee_ids = {employee["id"] for employee in grid.json()["employees"]}
    assert late_id not in employee_ids

    login_headers(client, "E001", "Employee123!")
    me = client.get("/api/v1/me/roster", params={"year": 2026, "month": 11})
    assert me.status_code == 200
    assert late_id not in {employee["id"] for employee in me.json()["employees"]}


def test_generated_roster_rotates_shifts_and_days_off(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    _set_requirements(client, headers, 1)  # 4 working, 2 off per day
    roster = _create_roster(client, headers)
    response = client.post(f"/api/v1/rosters/{roster['id']}/generate", headers=headers)
    assert response.status_code == 200
    assignments = response.json()["roster"]["assignments"]

    by_employee = Counter()
    for item in assignments:
        by_employee[(item["employee_id"], item["status_code"])] += 1

    for employee_id, _ in seeded["employees"]:
        codes = {code for (emp, code) in by_employee if emp == employee_id}
        assert {"G", "M", "A", "N", "O"} <= codes
