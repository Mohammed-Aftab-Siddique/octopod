from collections import Counter
from datetime import date

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


def test_generated_roster_keeps_fixed_shift_and_rotates_days_off(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    _set_requirements(client, headers, 1)  # 4 working, 2 off per day
    roster = _create_roster(client, headers)
    response = client.post(f"/api/v1/rosters/{roster['id']}/generate", headers=headers)
    assert response.status_code == 200
    assignments = response.json()["roster"]["assignments"]

    working_codes = {"G", "M", "A", "N"}
    by_employee: dict[int, Counter] = {}
    for item in assignments:
        by_employee.setdefault(item["employee_id"], Counter())[item["status_code"]] += 1

    for employee_id, _ in seeded["employees"]:
        counts = by_employee[employee_id]
        worked = {code: count for code, count in counts.items() if code in working_codes}
        assert worked, "every employee should work at least one day"
        # The employee is not rotated through every shift. Their primary shift
        # dominates; coverage corrections may still move them occasionally.
        primary, primary_days = max(worked.items(), key=lambda item: item[1])
        assert primary_days >= sum(worked.values()) / 2
        # Days off still rotate, so everyone receives at least one.
        assert counts["O"] > 0


def test_generation_never_recalls_planned_week_off(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    _set_requirements(client, headers, 1)
    roster = _create_roster(client, headers)

    # Put everyone off on the same weekend pair so coverage is impossible on
    # those days. The generator must keep the week-off and report a shortage
    # instead of recalling anybody. Start days are internal now, so set them
    # directly instead of going through the employee API.
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models.employee import Employee

    with get_sessionmaker()() as db:
        for employee in db.scalars(select(Employee)):
            employee.week_off_start_day = 5
        db.commit()

    generated = client.post(f"/api/v1/rosters/{roster['id']}/generate", headers=headers)
    assert generated.status_code == 200, generated.text
    result = generated.json()
    assignments = result["roster"]["assignments"]

    weekend_dates = {
        day["date"]
        for day in result["roster"]["days"]
        if date.fromisoformat(day["date"]).weekday() in (5, 6)
    }
    assert weekend_dates
    assert all(item["status_code"] == "O" for item in assignments if item["date"] in weekend_dates)
    shortage_dates = {shortage["date"] for shortage in result["shortages"]}
    assert weekend_dates <= shortage_dates


def test_delete_roster_removes_assignments_and_history(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")
    _set_requirements(client, headers, 1)
    roster = _create_roster(client, headers)
    generated = client.post(f"/api/v1/rosters/{roster['id']}/generate", headers=headers)
    assert generated.status_code == 200, generated.text

    deleted = client.delete(f"/api/v1/rosters/{roster['id']}", headers=headers)
    assert deleted.status_code == 204, deleted.text

    missing = client.get(f"/api/v1/rosters/{roster['id']}", headers=headers)
    assert missing.status_code == 404

    listed = client.get("/api/v1/rosters", headers=headers, params={"year": 2026, "month": 11})
    assert listed.status_code == 200
    assert listed.json() == []

    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models.roster import GenerationRun, RosterAssignment

    with get_sessionmaker()() as db:
        assert db.scalar(select(RosterAssignment.id)) is None
        assert db.scalar(select(GenerationRun.id)) is None


def test_fixed_shift_is_used_and_validated(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")

    invalid = client.patch(
        f"/api/v1/employees/{seeded['employees'][0][0]}",
        headers=headers,
        json={"default_shift": "O"},
    )
    assert invalid.status_code == 400

    for employee_id, _ in seeded["employees"]:
        response = client.patch(
            f"/api/v1/employees/{employee_id}",
            headers=headers,
            json={"default_shift": "G"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["default_shift"] == "G"

    requirements = [
        {"weekday": weekday, "status_code": "G", "required_count": 4} for weekday in range(7)
    ]
    saved = client.put(
        "/api/v1/reference/staffing-requirements",
        headers=headers,
        json={"requirements": requirements},
    )
    assert saved.status_code == 200, saved.text

    roster = _create_roster(client, headers)
    generated = client.post(f"/api/v1/rosters/{roster['id']}/generate", headers=headers)
    assert generated.status_code == 200, generated.text
    assignments = generated.json()["roster"]["assignments"]

    # Every working assignment is the fixed shift; nobody rotates to M/A/N.
    assert {item["status_code"] for item in assignments if item["status_code"] not in ("O",)} == {
        "G"
    }

    days_off = Counter(item["employee_id"] for item in assignments if item["status_code"] == "O")
    assert set(days_off) == {employee_id for employee_id, _ in seeded["employees"]}


def test_shift_preferences_stay_stable_across_the_period():
    from app.services.generation import (
        GenerationEmployee,
        GenerationInputs,
        GenerationStatus,
        compute_roster,
    )

    statuses = [
        GenerationStatus(code=code, is_working=code in {"G", "M", "A", "N"}, sort_order=order)
        for order, code in enumerate(["G", "M", "A", "N", "L", "CO", "O", "H"], start=1)
    ]
    employees = [
        GenerationEmployee(
            id=index,
            rotation_offset=index - 1,
            default_shift=("G", "M", "A", "N")[(index - 1) % 4],
            week_off_start_day=(index - 1) % 7,
        )
        for index in range(1, 13)
    ]
    requirements = {weekday: {code: 1 for code in ("G", "M", "A", "N")} for weekday in range(7)}
    rows, shortages, _ = compute_roster(
        GenerationInputs(
            year=2026,
            month=11,
            employees=employees,
            statuses=statuses,
            requirements=requirements,
        )
    )

    assert shortages == []
    by_employee: dict[int, Counter] = {}
    for row in rows:
        by_employee.setdefault(row["employee_id"], Counter())[row["status_code"]] += 1

    for employee in employees:
        worked = {
            code: count
            for code, count in by_employee[employee.id].items()
            if code in {"G", "M", "A", "N"}
        }
        # An explicit preference is not rotated through other shifts.
        assert set(worked) == {employee.default_shift}


def test_generation_uses_employee_week_off_pair(client, seeded):
    headers = login_headers(client, "admin@test.local", "Admin123!")

    # Week-offs are chosen per employee again. Put everyone on Sat–Sun so the
    # block is easy to verify.
    for employee_id, _ in seeded["employees"]:
        saved = client.patch(
            f"/api/v1/employees/{employee_id}",
            headers=headers,
            json={"week_off_start_day": 5},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["week_off_start_day"] == 5

    invalid = client.patch(
        f"/api/v1/employees/{seeded['employees'][0][0]}",
        headers=headers,
        json={"week_off_start_day": 7},
    )
    assert invalid.status_code == 422

    roster = _create_roster(client, headers)

    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models.employee import Employee

    with get_sessionmaker()() as db:
        start_days = {
            employee.id: employee.week_off_start_day for employee in db.scalars(select(Employee))
        }

    # Require exactly the number of people who are not on their planned
    # week-off, so the generator adds no extra days off and recalls nobody.
    requirements = []
    for weekday in range(7):
        off = sum(1 for start in start_days.values() if (weekday - start) % 7 < 2)
        requirements.append(
            {
                "weekday": weekday,
                "status_code": "G",
                "required_count": len(start_days) - off,
            }
        )
    response = client.put(
        "/api/v1/reference/staffing-requirements",
        headers=headers,
        json={"requirements": requirements},
    )
    assert response.status_code == 200, response.text

    generated = client.post(f"/api/v1/rosters/{roster['id']}/generate", headers=headers)
    assert generated.status_code == 200, generated.text
    assignments = generated.json()["roster"]["assignments"]

    for item in assignments:
        weekday = date.fromisoformat(item["date"]).weekday()
        is_week_off = (weekday - start_days[item["employee_id"]]) % 7 < 2
        assert item["status_code"] == ("O" if is_week_off else "G")
