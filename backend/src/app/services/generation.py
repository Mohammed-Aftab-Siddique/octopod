"""Deterministic, heuristic roster generation.

Every employee holds a **fixed shift** for the roster period (their
``default_shift``, or a balanced shift derived from ``rotation_offset`` when it
is unset). A period-level allocation moves employees between shifts only until
every shift has its configured headcount, so people stay on one shift instead
of rotating every day.

Staffing requirements are **shift headcounts for the whole period**, not daily
coverage. A requirement of six general-shift employees means six people belong
to the general shift; on any given day some of those six may be on their
week-off or leave. The generator therefore never adds extra days off just to
match a daily number, and it never recalls somebody from a planned week-off.

Week-offs are per employee: each person gets the ``WEEK_OFF_DAYS`` consecutive
weekdays starting at their configured ``week_off_start_day`` (for example
Saturday–Sunday or Monday–Tuesday).

If the configured headcounts need more people than are available, the gap is
reported as a shortage so the administrator can adjust staffing.

The implementation is intentionally a straightforward heuristic rather than an
optimiser. It is deterministic for identical inputs and reports shortages
instead of silently producing an invalid roster.

Input loading, pure computation, and persistence are separated so the compute
step can be moved to the ``Generator`` Durable Object if the Worker CPU budget
requires it.
"""

from collections import Counter
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

WEEK_OFF_DAYS = 2
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
    week_off_start_day: int = 0


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
    requirements: dict[str, int] = field(default_factory=dict)
    availability: dict[tuple[int, date], str] = field(default_factory=dict)
    holidays: dict[date, str] = field(default_factory=dict)

    @property
    def bounds(self) -> tuple[date, date]:
        return month_bounds(self.year, self.month)


def _load_requirements(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(StaffingRequirement, ShiftStatus)
        .join(ShiftStatus, StaffingRequirement.status_id == ShiftStatus.id)
        .where(ShiftStatus.is_working.is_(True))
    ).all()
    return {status.code: requirement.required_count for requirement, status in rows}


def load_generation_inputs(db: Session, period: RosterPeriod) -> GenerationInputs:
    """Load every input the pure generator needs (five queries)."""

    first, last = month_bounds(period.year, period.month)
    employees = [
        GenerationEmployee(
            id=employee.id,
            rotation_offset=employee.rotation_offset,
            default_shift=employee.default_shift,
            week_off_start_day=employee.week_off_start_day,
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
                "week_off_start_day": employee.week_off_start_day,
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
        "requirements": dict(inputs.requirements),
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
                week_off_start_day=int(
                    item.get("week_off_start_day", int(item["rotation_offset"]) % 7)
                ),
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
            str(code): int(count) for code, count in payload.get("requirements", {}).items()
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


def _fixed_shift(employee: GenerationEmployee, working_codes: list[str]) -> str:
    """Resolve the employee's primary shift for the period."""

    if employee.default_shift is not None and employee.default_shift in working_codes:
        return employee.default_shift
    return working_codes[employee.rotation_offset % len(working_codes)]


def _is_week_off(employee: GenerationEmployee, current: date) -> bool:
    """Whether ``current`` falls in the employee's consecutive week-off block."""

    return (current.weekday() - employee.week_off_start_day) % 7 < WEEK_OFF_DAYS


def _assign_base_shifts(
    employees: list[GenerationEmployee],
    working_codes: list[str],
    requirements: dict[str, int],
) -> dict[int, str]:
    """Pick one shift per employee for the whole period.

    Each configured requirement is a minimum headcount for that shift. Employees
    start on their preferred shift and are only moved out of shifts that exceed
    their headcount. Auto-assigned employees move before explicit preferences,
    and any extra employees stay on their preferred shift.
    """

    preferred = {employee.id: _fixed_shift(employee, working_codes) for employee in employees}
    if not requirements or not employees:
        return preferred

    targets = {code: max(0, requirements.get(code, 0)) for code in working_codes}
    if not any(targets.values()):
        return preferred

    base = dict(preferred)
    counts = Counter(base.values())
    for deficit in working_codes:
        while counts[deficit] < targets[deficit]:
            candidates = [
                employee
                for employee in employees
                if counts[base[employee.id]] > targets.get(base[employee.id], 0)
            ]
            if not candidates:
                break
            mover = min(
                candidates,
                key=lambda employee: (
                    employee.default_shift is not None,
                    employee.rotation_offset,
                    employee.id,
                ),
            )
            counts[base[mover.id]] -= 1
            base[mover.id] = deficit
            counts[deficit] += 1
    return base


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

    configured = {
        code: count
        for code, count in inputs.requirements.items()
        if code in working_codes and count > 0
    }
    if not configured:
        warnings.append(
            "No staffing requirements configured. Employees keep their preferred shifts."
        )

    availability = inputs.availability
    holidays = inputs.holidays

    # One stable shift per employee for the period. Employees only move when a
    # shift is below its configured headcount.
    base_shift = _assign_base_shifts(employees, working_codes, configured)

    shortages: list[ShortageRow] = []
    if configured:
        assigned_counts = Counter(base_shift.values())
        for code in working_codes:
            required = configured.get(code, 0)
            assigned = assigned_counts.get(code, 0)
            if assigned < required:
                shortages.append(
                    {
                        "date": first.isoformat(),
                        "status_code": code,
                        "required": required,
                        "assigned": assigned,
                    }
                )

    rows: list[AssignmentRow] = []
    for ordinal in range(first.toordinal(), last.toordinal() + 1):
        current = date.fromordinal(ordinal)
        if current in holidays:
            for employee in employees:
                rows.append(
                    {"employee_id": employee.id, "date": current, "status_code": HOLIDAY_CODE}
                )
            continue

        for employee in employees:
            kind = availability.get((employee.id, current))
            if kind == AvailabilityKind.leave:
                code = LEAVE_CODE
            elif kind == AvailabilityKind.comp_off:
                code = COMP_OFF_CODE
            elif kind == AvailabilityKind.unavailable or _is_week_off(employee, current):
                code = OFF_CODE
            else:
                code = base_shift[employee.id]
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
