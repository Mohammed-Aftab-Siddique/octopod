"""Deterministic, heuristic roster generation.

Every employee holds a **fixed shift** for the roster period (their
``default_shift``, or a balanced shift derived from ``rotation_offset`` when it
is unset). Week-offs rotate independently: each employee gets a block of
consecutive days off per week, staggered by ``rotation_offset``.

Staffing requirements are the correction layer. They can add an extra day off
or recall an employee from a planned day off, and they move employees between
shifts when the fixed-shift mix does not cover a shift. Fairness counters keep
these corrections deterministic and balanced.

The implementation is intentionally a straightforward heuristic rather than an
optimiser. It is deterministic for identical inputs and reports shortages
instead of silently producing an invalid roster.

Input loading, pure computation, and persistence are separated so the compute
step can be moved to the ``Generator`` Durable Object if the Worker CPU budget
requires it.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.availability import Availability, AvailabilityKind
from app.models.employee import Employee
from app.models.reference import Holiday, ShiftStatus, StaffingRequirement
from app.models.roster import RosterPeriod
from app.services.rosters import month_bounds

LEAVE_CODE = "L"
COMP_OFF_CODE = "CO"
OFF_CODE = "O"
HOLIDAY_CODE = "H"


class AssignmentRow(TypedDict):
    employee_id: int
    date: date
    status_code: str


class ShortageRow(TypedDict):
    date: str
    status_code: str
    required: int
    assigned: int


@dataclass(frozen=True)
class GenerationEmployee:
    id: int
    rotation_offset: int
    default_shift: str | None = None
    weekly_off_days: int = 2


@dataclass(frozen=True)
class GenerationStatus:
    code: str
    is_working: bool
    sort_order: int


@dataclass
class GenerationInputs:
    year: int
    month: int
    employees: list[GenerationEmployee] = field(default_factory=list)
    statuses: list[GenerationStatus] = field(default_factory=list)
    requirements: dict[int, dict[str, int]] = field(default_factory=dict)
    availability: dict[tuple[int, date], str] = field(default_factory=dict)
    holidays: dict[date, str] = field(default_factory=dict)

    @property
    def bounds(self) -> tuple[date, date]:
        return month_bounds(self.year, self.month)


def _load_requirements(db: Session) -> dict[int, dict[str, int]]:
    requirements: dict[int, dict[str, int]] = defaultdict(dict)
    rows = db.execute(
        select(StaffingRequirement, ShiftStatus)
        .join(ShiftStatus, StaffingRequirement.status_id == ShiftStatus.id)
        .where(ShiftStatus.is_working.is_(True))
    ).all()
    for requirement, status in rows:
        requirements[requirement.weekday][status.code] = requirement.required_count
    return requirements


def load_generation_inputs(db: Session, period: RosterPeriod) -> GenerationInputs:
    """Load every input the pure generator needs (five queries)."""

    first, last = month_bounds(period.year, period.month)
    employees = [
        GenerationEmployee(
            id=employee.id,
            rotation_offset=employee.rotation_offset,
            default_shift=employee.default_shift,
            weekly_off_days=employee.weekly_off_days,
        )
        for employee in db.scalars(
            select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.id)
        )
    ]
    statuses = [
        GenerationStatus(
            code=status.code,
            is_working=status.is_working,
            sort_order=status.sort_order,
        )
        for status in db.scalars(select(ShiftStatus).order_by(ShiftStatus.sort_order))
    ]
    availability = {
        (row.employee_id, row.date): row.kind.value
        for row in db.scalars(
            select(Availability).where(Availability.date >= first, Availability.date <= last)
        )
    }
    holidays = {
        row.date: row.label
        for row in db.scalars(select(Holiday).where(Holiday.date >= first, Holiday.date <= last))
    }
    return GenerationInputs(
        year=period.year,
        month=period.month,
        employees=employees,
        statuses=statuses,
        requirements=_load_requirements(db),
        availability=availability,
        holidays=holidays,
    )


def inputs_to_payload(inputs: GenerationInputs) -> dict[str, Any]:
    """Serialize inputs for the Generator Durable Object."""

    return {
        "year": inputs.year,
        "month": inputs.month,
        "employees": [
            {
                "id": employee.id,
                "rotation_offset": employee.rotation_offset,
                "default_shift": employee.default_shift,
                "weekly_off_days": employee.weekly_off_days,
            }
            for employee in inputs.employees
        ],
        "statuses": [
            {
                "code": status.code,
                "is_working": status.is_working,
                "sort_order": status.sort_order,
            }
            for status in inputs.statuses
        ],
        "requirements": {str(weekday): values for weekday, values in inputs.requirements.items()},
        "availability": [
            {"employee_id": employee_id, "date": day.isoformat(), "kind": kind}
            for (employee_id, day), kind in inputs.availability.items()
        ],
        "holidays": [
            {"date": day.isoformat(), "label": label} for day, label in inputs.holidays.items()
        ],
    }


def inputs_from_payload(payload: dict[str, Any]) -> GenerationInputs:
    return GenerationInputs(
        year=int(payload["year"]),
        month=int(payload["month"]),
        employees=[
            GenerationEmployee(
                id=int(item["id"]),
                rotation_offset=int(item["rotation_offset"]),
                default_shift=item.get("default_shift"),
                weekly_off_days=int(item.get("weekly_off_days", 2)),
            )
            for item in payload.get("employees", [])
        ],
        statuses=[
            GenerationStatus(
                code=str(item["code"]),
                is_working=bool(item["is_working"]),
                sort_order=int(item["sort_order"]),
            )
            for item in payload.get("statuses", [])
        ],
        requirements={
            int(weekday): {str(code): int(count) for code, count in values.items()}
            for weekday, values in payload.get("requirements", {}).items()
        },
        availability={
            (int(item["employee_id"]), date.fromisoformat(item["date"])): str(item["kind"])
            for item in payload.get("availability", [])
        },
        holidays={
            date.fromisoformat(item["date"]): str(item["label"])
            for item in payload.get("holidays", [])
        },
    )


def _default_requirements(working_codes: list[str], employee_count: int) -> dict[str, int]:
    if not working_codes:
        return {}
    working_target = max(len(working_codes), round(max(employee_count, 1) * 0.8))
    base = max(1, working_target // len(working_codes))
    result = {code: base for code in working_codes}
    result[working_codes[0]] += max(0, working_target - base * len(working_codes))
    return result


def _fixed_shift(employee: GenerationEmployee, working_codes: list[str]) -> str:
    """Resolve the employee's primary shift for the period."""

    if employee.default_shift is not None and employee.default_shift in working_codes:
        return employee.default_shift
    return working_codes[employee.rotation_offset % len(working_codes)]


def _prefers_day_off(employee: GenerationEmployee, current: date) -> bool:
    """Whether the employee's weekly off block covers ``current``."""

    days = employee.weekly_off_days
    if days <= 0:
        return False
    if days >= 7:
        return True
    start = employee.rotation_offset % 7
    return (current.weekday() - start) % 7 < days


def compute_roster(
    inputs: GenerationInputs,
) -> tuple[list[AssignmentRow], list[ShortageRow], list[str]]:
    """Run the pure scheduling algorithm. No database access."""

    first, last = inputs.bounds
    employees = inputs.employees
    status_by_code = {status.code: status for status in inputs.statuses}
    working_codes = [
        status.code
        for status in inputs.statuses
        if status.is_working and status.code != HOLIDAY_CODE
    ]
    warnings: list[str] = []
    if not employees:
        return [], [], ["No active employees. Add employees before generating a roster."]
    if not working_codes:
        raise RuntimeError("No working shifts are configured")
    if OFF_CODE not in status_by_code:
        raise RuntimeError("The week-off status (O) is not configured")
    if HOLIDAY_CODE not in status_by_code:
        raise RuntimeError("The holiday status (H) is not configured")

    configured = inputs.requirements
    using_defaults = not configured
    if using_defaults:
        warnings.append(
            "No staffing requirements configured. Default coverage was derived from team size."
        )

    availability = inputs.availability
    holidays = inputs.holidays

    shift_counts: dict[int, dict[str, int]] = {
        employee.id: defaultdict(int) for employee in employees
    }
    work_counts: dict[int, int] = {employee.id: 0 for employee in employees}
    off_counts: dict[int, int] = {employee.id: 0 for employee in employees}

    rows: list[AssignmentRow] = []
    shortages: list[ShortageRow] = []

    for ordinal in range(first.toordinal(), last.toordinal() + 1):
        current = date.fromordinal(ordinal)
        holiday_label = holidays.get(current)

        if holiday_label is not None:
            for employee in employees:
                rows.append(
                    {"employee_id": employee.id, "date": current, "status_code": HOLIDAY_CODE}
                )
            continue

        base_rows: list[AssignmentRow] = []
        eligible: list[GenerationEmployee] = []
        for employee in employees:
            kind = availability.get((employee.id, current))
            if kind == AvailabilityKind.leave:
                base_rows.append(
                    {"employee_id": employee.id, "date": current, "status_code": LEAVE_CODE}
                )
            elif kind == AvailabilityKind.comp_off:
                base_rows.append(
                    {"employee_id": employee.id, "date": current, "status_code": COMP_OFF_CODE}
                )
            elif kind in (AvailabilityKind.week_off, AvailabilityKind.unavailable):
                base_rows.append(
                    {"employee_id": employee.id, "date": current, "status_code": OFF_CODE}
                )
                off_counts[employee.id] += 1
            else:
                eligible.append(employee)

        if not eligible:
            rows.extend(base_rows)
            continue

        if using_defaults:
            required = _default_requirements(working_codes, len(employees))
        else:
            required = dict(configured.get(current.weekday(), {}))
        required = {code: count for code, count in required.items() if count > 0}

        # Fixed shift for the period; days off come from the weekly block.
        preferred = {employee.id: _fixed_shift(employee, working_codes) for employee in eligible}

        off: set[int] = {
            employee.id for employee in eligible if _prefers_day_off(employee, current)
        }
        pool: list[GenerationEmployee] = [
            employee for employee in eligible if employee.id not in off
        ]
        required_total = sum(required.values())

        # Too many people available: add days off, preferring employees who
        # have had the fewest so far.
        while required_total > 0 and len(pool) > required_total:
            candidate = min(
                pool,
                key=lambda employee: (
                    off_counts[employee.id],
                    employee.rotation_offset,
                    employee.id,
                ),
            )
            pool.remove(candidate)
            off.add(candidate.id)

        # Too few people available: recall people from their planned day off,
        # preferring employees who have already had the most days off.
        while len(pool) < required_total:
            candidates = [employee for employee in eligible if employee.id in off]
            if not candidates:
                break
            recalled = max(
                candidates,
                key=lambda employee: (
                    off_counts[employee.id],
                    employee.rotation_offset,
                    employee.id,
                ),
            )
            off.discard(recalled.id)
            pool.append(recalled)

        assignments: dict[int, str] = {}
        unassigned = sorted(pool, key=lambda employee: employee.id)

        for code in working_codes:
            need = required.get(code, 0)
            if need <= 0:
                continue
            candidates = sorted(
                unassigned,
                key=lambda employee: (
                    preferred[employee.id] != code,
                    shift_counts[employee.id][code],
                    work_counts[employee.id],
                    employee.rotation_offset,
                    employee.id,
                ),
            )
            for employee in candidates[:need]:
                assignments[employee.id] = code
                shift_counts[employee.id][code] += 1
                work_counts[employee.id] += 1
            unassigned = [employee for employee in unassigned if employee.id not in assignments]

        # Any remaining available employees work their fixed shift.
        for employee in unassigned:
            code = preferred[employee.id]
            assignments[employee.id] = code
            shift_counts[employee.id][code] += 1
            work_counts[employee.id] += 1

        for code, need in required.items():
            assigned = sum(1 for value in assignments.values() if value == code)
            if assigned < need:
                shortages.append(
                    {
                        "date": current.isoformat(),
                        "status_code": code,
                        "required": need,
                        "assigned": assigned,
                    }
                )

        for employee_id in off:
            off_counts[employee_id] += 1

        rows.extend(base_rows)
        for employee in eligible:
            code = assignments.get(employee.id, OFF_CODE)
            rows.append({"employee_id": employee.id, "date": current, "status_code": code})

    warnings.append(
        "Review the draft before publishing. Automated rosters are never published "
        "without administrator approval."
    )
    return rows, shortages, warnings


def generate_roster(
    db: Session, period: RosterPeriod
) -> tuple[list[AssignmentRow], list[ShortageRow], list[str]]:
    """Load inputs and compute the roster in-process."""

    return compute_roster(load_generation_inputs(db, period))
