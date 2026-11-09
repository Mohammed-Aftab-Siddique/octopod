from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.availability import Availability, AvailabilityKind
from app.models.employee import Employee
from app.models.reference import ShiftStatus, StaffingRequirement
from app.models.user import Role, User
from app.services import rosters
from app.services.generation import generate_roster

STATUS_SEED = [
    ("G", "General shift", "#E5E7EB", "#111827", True, 1),
    ("M", "Morning shift", "#BBF7D0", "#14532D", True, 2),
    ("A", "Afternoon shift", "#BFDBFE", "#1E3A8A", True, 3),
    ("N", "Night shift", "#FDE68A", "#78350F", True, 4),
    ("L", "Leave", "#FECACA", "#7F1D1D", False, 5),
    ("CO", "Compensatory off", "#FDBA74", "#7C2D12", False, 6),
    ("O", "Week-off / day-off", "#F3F4F6", "#374151", False, 7),
    ("H", "Holiday", "#DDD6FE", "#4C1D95", False, 8),
]

DEMO_EMPLOYEES = [
    "Atharv Prawal",
    "Prajwal",
    "Aftab",
    "Sarjeel",
    "Visnopreyaa",
    "Shantanu Prakash",
    "Srinivas",
    "Zainab",
    "Jeelani",
    "Shabanas",
    "Sumit",
    "Sidhant",
    "Prathamesh",
    "Parvez",
    "Tara",
    "Gautam",
    "Kumar",
]


def ensure_statuses(db: Session) -> dict[str, ShiftStatus]:
    existing = {status.code: status for status in db.scalars(select(ShiftStatus))}
    for code, label, color, text_color, is_working, sort_order in STATUS_SEED:
        if code not in existing:
            status = ShiftStatus(
                code=code,
                label=label,
                color=color,
                text_color=text_color,
                is_working=is_working,
                sort_order=sort_order,
            )
            db.add(status)
            existing[code] = status
    db.commit()
    return {
        code: db.scalar(select(ShiftStatus).where(ShiftStatus.code == code)) for code in existing
    }


def ensure_staffing_requirements(db: Session) -> None:
    if db.scalar(select(StaffingRequirement.id)):
        return
    statuses = {status.code: status for status in db.scalars(select(ShiftStatus))}
    defaults = {
        0: {"G": 4, "M": 3, "A": 3, "N": 3},
        1: {"G": 4, "M": 3, "A": 3, "N": 3},
        2: {"G": 4, "M": 3, "A": 3, "N": 3},
        3: {"G": 4, "M": 3, "A": 3, "N": 3},
        4: {"G": 4, "M": 3, "A": 3, "N": 3},
        5: {"G": 3, "M": 2, "A": 2, "N": 2},
        6: {"G": 3, "M": 2, "A": 2, "N": 2},
    }
    for weekday, values in defaults.items():
        for code, count in values.items():
            db.add(
                StaffingRequirement(
                    weekday=weekday, status_id=statuses[code].id, required_count=count
                )
            )
    db.commit()


async def seed_demo(db: Session) -> None:
    ensure_statuses(db)
    ensure_staffing_requirements(db)

    if db.scalar(select(User.id).where(User.role == Role.admin)):
        return

    admin = User(
        email="admin@example.com",
        password_hash=hash_password("Admin123!"),
        role=Role.admin,
        is_active=True,
    )
    db.add(admin)
    db.flush()

    employees: list[Employee] = []
    for index, name in enumerate(DEMO_EMPLOYEES, start=1):
        email = f"{name.split()[0].lower()}@example.com"
        employee = Employee(
            employee_code=f"EMP{index:03d}",
            full_name=name,
            email=email,
            rotation_offset=index - 1,
            is_active=True,
        )
        db.add(employee)
        db.flush()
        db.add(
            User(
                email=email,
                password_hash=hash_password("Employee123!"),
                role=Role.employee,
                employee_id=employee.id,
                is_active=True,
            )
        )
        employees.append(employee)
    db.commit()

    today = date.today()
    # A small amount of approved leave makes the demo meaningful.
    for employee, day_range in (
        (employees[3], (12, 14)),
        (employees[8], (20, 21)),
        (employees[11], (5, 6)),
    ):
        for day in range(day_range[0], day_range[1] + 1):
            try:
                leave_date = date(today.year, today.month, day)
            except ValueError:
                continue
            db.add(
                Availability(
                    employee_id=employee.id,
                    date=leave_date,
                    kind=AvailabilityKind.leave,
                    note="Approved leave",
                    created_by=admin.id,
                )
            )
    db.commit()

    period, _ = await rosters.get_or_create_draft(db, today.year, today.month, admin.id)
    rows, shortages, warnings = generate_roster(db, period)
    await rosters.replace_assignments(
        db, period, [(row["employee_id"], row["date"], row["status_code"]) for row in rows]
    )
    await rosters.record_generation_run(
        db, period, user_id=admin.id, shortages=shortages, warnings=warnings
    )
    await rosters.publish_period(db, period, admin.id)
