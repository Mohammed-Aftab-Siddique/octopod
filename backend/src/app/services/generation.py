"""Deterministic, heuristic roster generation.

Every employee holds a **fixed shift** for the roster period (their
``default_shift``, or a balanced shift derived from ``rotation_offset`` when it
is unset). A period-level allocation moves employees between shifts only when
the preferred shift mix cannot cover the configured demand, so people stay on
one shift instead of rotating every day.

Week-offs use the organisation-wide ``consecutive_off_days`` policy (exactly
that many consecutive weekdays each week). Each employee's block starts at
``week_off_start_day``, which is staggered automatically from the rotation
offset and is no longer edited per employee.

Staffing requirements are the correction layer. They can add an extra day off
and they move employees between shifts when the fixed-shift mix does not cover
a shift. An employee's planned week-off block is never recalled: if
requirements ask for more people than are available, the gap is reported as a
shortage so the administrator can adjust staffing or the global week-off
policy. Fairness counters keep these corrections deterministic and balanced.

The implementation is intentionally a straightforward heuristic rather than an
optimiser. It is deterministic for identical inputs and reports shortages
instead of silently producing an invalid roster.

Input loading, pure computation, and persistence are separated so the compute
step can be moved to the ``Generator`` Durable Object if the Worker CPU budget
requires it.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.availability import Availability, AvailabilityKind
from app.models.employee import Employee
from app.models.reference import Holiday, ShiftStatus, StaffingRequirement
from app.models.roster import RosterPeriod
from app.services.reference import get_consecutive_off_days
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
    requirements: dict[int, dict[str, int]] = field(default_factory=dict)
    availability: dict[tuple[int, date], str] = field(default_factory=dict)
    holidays: dict[date, str] = field(default_factory=dict)
    consecutive_off_days: int = 2

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
        consecutive_off_days=get_consecutive_off_days(db),
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
        "requirements": {str(weekday): values for weekday, values in inputs.requirements.items()},
        "availability": [
            {"employee_id": employee_id, "date": day.isoformat(), "kind": kind}
            for (employee_id, day), kind in inputs.availability.items()
        ],
        "holidays": [
            {"date": day.isoformat(), "label": label} for day, label in inputs.holidays.items()
        ],
        "consecutive_off_days": inputs.consecutive_off_days,
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
        consecutive_off_days=int(payload.get("consecutive_off_days", 2)),
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


def _is_week_off(employee: GenerationEmployee, current: date, consecutive_off_days: int) -> bool:
    """Whether ``current`` falls in the employee's consecutive week-off block."""

    return (current.weekday() - employee.week_off_start_day) % 7 < consecutive_off_days


def _period_targets(
    requirements: dict[int, dict[str, int]],
    working_codes: list[str],
    employee_count: int,
) -> dict[str, int]:
    """Allocate employee headcount to shifts in proportion to weekly demand."""

    demand = {
        code: sum(requirements.get(weekday, {}).get(code, 0) for weekday in range(7))
        for code in working_codes
    }
    total = sum(demand.values())
    if total <= 0 or employee_count <= 0:
        return {}

    raw = {code: demand[code] * employee_count / total for code in working_codes}
    targets = {code: int(raw[code]) for code in working_codes}
    remaining = employee_count - sum(targets.values())
    order = sorted(
        working_codes,
        key=lambda code: (-(raw[code] - targets[code]), working_codes.index(code)),
    )
    for index in range(remaining):
        targets[order[index % len(order)]] += 1
    return targets


def _assign_base_shifts(
    employees: list[GenerationEmployee],
    working_codes: list[str],
    requirements: dict[int, dict[str, int]],
) -> dict[int, str]:
    """Pick one shift per employee for the whole period.

    Employees start on their preferred shift. When that shift is over-supplied
    relative to the period demand, auto-assigned employees are moved first so
    explicit shift preferences survive wherever coverage allows.
    """

    preferred = {employee.id: _fixed_shift(employee, working_codes) for employee in employees}
    if not requirements or not employees:
        return preferred

    targets = _period_targets(requirements, working_codes, len(employees))
    if not targets:
        return preferred

    base = dict(preferred)
    counts = Counter(base.values())
    for deficit in working_codes:
        while counts[deficit] < targets[deficit]:
            candidates = [
                employee
                for employee in employees
                if counts[base[employee.id]] > targets[base[employee.id]]
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

    configured = inputs.requirements
    using_defaults = not configured
    if using_defaults:
        warnings.append(
            "No staffing requirements configured. Default coverage was derived from team size."
        )

    availability = inputs.availability
    holidays = inputs.holidays

    off_counts: dict[int, int] = {employee.id: 0 for employee in employees}
    move_counts: dict[int, int] = {employee.id: 0 for employee in employees}

    # One stable shift per employee for the period. Employees are only moved
    # between shifts when their preferred shift is over-subscribed.
    base_shift = _assign_base_shifts(employees, working_codes, configured)
    consecutive_off_days = min(max(inputs.consecutive_off_days, 1), 6)

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
            elif kind == AvailabilityKind.unavailable:
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
        required = {
            code: count for code, count in required.items() if count > 0 and code in working_codes
        }

        week_off = {
            employee.id
            for employee in eligible
            if _is_week_off(employee, current, consecutive_off_days)
        }
        pool = [employee for employee in eligible if employee.id not in week_off]

        by_base: dict[str, list[GenerationEmployee]] = defaultdict(list)
        for employee in pool:
            by_base[base_shift[employee.id]].append(employee)

        assignments: dict[int, str] = {}
        off: set[int] = set(week_off)
        shortfall: dict[str, int] = {}

        # Give each shift the people whose base shift matches it. When a shift
        # has more people than needed, the people with the most days off so far
        # work first so off days stay balanced.
        for code in working_codes:
            need = required.get(code, 0)
            group = by_base.get(code, [])
            group.sort(
                key=lambda employee: (
                    -off_counts[employee.id],
                    move_counts[employee.id],
                    employee.rotation_offset,
                    employee.id,
                )
            )
            for employee in group[:need]:
                assignments[employee.id] = code
            for employee in group[need:]:
                off.add(employee.id)
            if len(group) < need:
                shortfall[code] = need - len(group)

        # Cover deficits with available people whose own shift has a surplus.
        # Planned week-offs are never used as cover.
        for code in working_codes:
            deficit = shortfall.get(code, 0)
            while deficit > 0:
                candidates = [
                    employee
                    for employee in pool
                    if employee.id in off and employee.id not in week_off
                ]
                if not candidates:
                    break

                def _cover_rank(
                    employee: GenerationEmployee,
                    by_base: dict[str, list[GenerationEmployee]] = by_base,
                    required: dict[str, int] = required,
                ) -> tuple:
                    base_code = base_shift[employee.id]
                    surplus = len(by_base.get(base_code, [])) - required.get(base_code, 0)
                    return (
                        surplus <= 0,
                        -surplus,
                        -off_counts[employee.id],
                        move_counts[employee.id],
                        employee.rotation_offset,
                        employee.id,
                    )

                mover = min(candidates, key=_cover_rank)
                off.discard(mover.id)
                assignments[mover.id] = code
                move_counts[mover.id] += 1
                deficit -= 1

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
