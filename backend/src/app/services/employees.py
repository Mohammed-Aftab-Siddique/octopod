from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password_remote
from app.db.d1 import d1_batch, has_binding, multi_row_insert, utcnow_text
from app.models.availability import Availability, AvailabilityKind
from app.models.employee import Employee
from app.models.reference import ShiftStatus
from app.models.user import Role, User, UserSession
from app.schemas.employee import EmployeeCreate, EmployeeUpdate

DEFAULT_PASSWORD = "Employee123!"


def _normalise_default_shift(db: Session, code: str | None) -> str | None:
    """Return a canonical working shift code, or ``None`` for auto-assignment."""

    if code is None:
        return None
    normalised = code.strip().upper()
    shift_status = db.scalar(
        select(ShiftStatus).where(func.lower(ShiftStatus.code) == normalised.lower())
    )
    if shift_status is None or not shift_status.is_working:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Shift {normalised} is not a working shift",
        )
    return shift_status.code


async def _revoke_sessions(db: Session, user_id: int) -> None:
    for session in db.scalars(select(UserSession).where(UserSession.user_id == user_id)):
        db.delete(session)


def _is_unique_violation(exc: Exception) -> bool:
    message = str(exc).upper()
    return "UNIQUE" in message or "CONSTRAINT" in message


def get_employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


def list_employees(db: Session, *, include_inactive: bool = True) -> list[Employee]:
    stmt = select(Employee).order_by(Employee.full_name)
    if not include_inactive:
        stmt = stmt.where(Employee.is_active.is_(True))
    return list(db.scalars(stmt))


async def create_employee(
    db: Session, payload: EmployeeCreate, created_by: int | None, *, env=None
) -> Employee:
    code = payload.employee_code.strip().upper()
    email = payload.email.lower()
    if db.scalar(select(Employee.id).where(func.lower(Employee.employee_code) == code.lower())):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Employee code already exists"
        )
    if db.scalar(select(Employee.id).where(func.lower(Employee.email) == email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Employee email already exists"
        )

    max_offset = db.scalar(select(func.max(Employee.rotation_offset))) or 0
    rotation_offset = (
        payload.rotation_offset if payload.rotation_offset is not None else max_offset + 1
    )
    default_shift = _normalise_default_shift(db, payload.default_shift)
    week_off_start_day = (
        payload.week_off_start_day
        if payload.week_off_start_day is not None
        else rotation_offset % 7
    )
    password_hash = await hash_password_remote(env, payload.password or DEFAULT_PASSWORD)

    if has_binding(env):
        now = utcnow_text()
        # Insert the employee and the linked account in one atomic batch. The
        # user row resolves the new employee id with a subquery so no round-trip
        # is needed to read RETURNING.
        statements = [
            (
                "INSERT INTO employees "
                "(employee_code, full_name, email, is_active, rotation_offset, "
                "default_shift, week_off_start_day, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)",
                [
                    code,
                    payload.full_name.strip(),
                    email,
                    rotation_offset,
                    default_shift,
                    week_off_start_day,
                    now,
                    now,
                ],
            ),
            (
                "INSERT INTO users "
                "(email, password_hash, role, is_active, employee_id, created_at, updated_at) "
                "VALUES (?, ?, 'employee', 1, "
                "(SELECT id FROM employees WHERE employee_code = ?), ?, ?)",
                [email, password_hash, code, now, now],
            ),
        ]
        try:
            await d1_batch(env, statements)
        except Exception as exc:  # D1 surfaces SQLite constraint errors as JS errors
            if _is_unique_violation(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Employee code or email already exists",
                ) from exc
            raise
        db.expire_all()
        employee = db.scalar(select(Employee).where(Employee.employee_code == code))
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Employee could not be created",
            )
        return employee

    employee = Employee(
        employee_code=code,
        full_name=payload.full_name.strip(),
        email=email,
        rotation_offset=rotation_offset,
        default_shift=default_shift,
        week_off_start_day=week_off_start_day,
    )
    db.add(employee)
    db.flush()

    db.add(
        User(
            email=email,
            password_hash=password_hash,
            role=Role.employee,
            employee_id=employee.id,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Employee code or email already exists"
        ) from exc
    db.refresh(employee)
    return employee


async def update_employee(
    db: Session, employee: Employee, payload: EmployeeUpdate, *, env=None
) -> Employee:
    code = None
    if payload.employee_code is not None:
        code = payload.employee_code.strip().upper()
        existing = db.scalar(
            select(Employee.id).where(
                func.lower(Employee.employee_code) == code.lower(), Employee.id != employee.id
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Employee code already exists"
            )

    email = None
    if payload.email is not None:
        email = payload.email.lower()
        existing = db.scalar(
            select(Employee.id).where(
                func.lower(Employee.email) == email, Employee.id != employee.id
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Employee email already exists"
            )

    default_shift: str | None = None
    if "default_shift" in payload.model_fields_set:
        default_shift = _normalise_default_shift(db, payload.default_shift)

    if has_binding(env):
        now = utcnow_text()
        employee_sets = ["updated_at = ?"]
        employee_params: list = [now]
        if code is not None:
            employee_sets.append("employee_code = ?")
            employee_params.append(code)
        if payload.full_name is not None:
            employee_sets.append("full_name = ?")
            employee_params.append(payload.full_name.strip())
        if email is not None:
            employee_sets.append("email = ?")
            employee_params.append(email)
        if payload.rotation_offset is not None:
            employee_sets.append("rotation_offset = ?")
            employee_params.append(payload.rotation_offset)
        if "default_shift" in payload.model_fields_set:
            employee_sets.append("default_shift = ?")
            employee_params.append(default_shift)
        if payload.week_off_start_day is not None:
            employee_sets.append("week_off_start_day = ?")
            employee_params.append(payload.week_off_start_day)
        if payload.is_active is not None:
            employee_sets.append("is_active = ?")
            employee_params.append(1 if payload.is_active else 0)
        employee_params.append(employee.id)

        statements: list[tuple[str, list]] = [
            (f"UPDATE employees SET {', '.join(employee_sets)} WHERE id = ?", employee_params)
        ]

        user = employee.user
        if user is not None:
            user_sets = ["updated_at = ?"]
            user_params: list = [now]
            if email is not None:
                user_sets.append("email = ?")
                user_params.append(email)
            if payload.is_active is not None:
                user_sets.append("is_active = ?")
                user_params.append(1 if payload.is_active else 0)
            user_params.append(user.id)
            statements.append(
                (f"UPDATE users SET {', '.join(user_sets)} WHERE id = ?", user_params)
            )
            if payload.is_active is False:
                statements.append(("DELETE FROM user_sessions WHERE user_id = ?", [user.id]))

        try:
            await d1_batch(env, statements)
        except Exception as exc:
            if _is_unique_violation(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Employee code or email already exists",
                ) from exc
            raise
        db.expire_all()
        return get_employee(db, employee.id)

    if code is not None:
        employee.employee_code = code
    if payload.full_name is not None:
        employee.full_name = payload.full_name.strip()
    if email is not None:
        employee.email = email
        if employee.user:
            employee.user.email = email
    if payload.rotation_offset is not None:
        employee.rotation_offset = payload.rotation_offset
    if "default_shift" in payload.model_fields_set:
        employee.default_shift = default_shift
    if payload.week_off_start_day is not None:
        employee.week_off_start_day = payload.week_off_start_day
    if payload.is_active is not None:
        employee.is_active = payload.is_active
        if employee.user:
            employee.user.is_active = payload.is_active
            if not payload.is_active:
                await _revoke_sessions(db, employee.user.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Employee code or email already exists"
        ) from exc
    db.refresh(employee)
    return employee


async def deactivate_employee(db: Session, employee: Employee, *, env=None) -> Employee:
    if has_binding(env):
        now = utcnow_text()
        statements: list[tuple[str, list]] = [
            ("UPDATE employees SET is_active = 0, updated_at = ? WHERE id = ?", [now, employee.id])
        ]
        user = employee.user
        if user is not None:
            statements.append(
                ("UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?", [now, user.id])
            )
            statements.append(("DELETE FROM user_sessions WHERE user_id = ?", [user.id]))
        await d1_batch(env, statements)
        db.expire_all()
        return get_employee(db, employee.id)

    employee.is_active = False
    if employee.user:
        employee.user.is_active = False
        await _revoke_sessions(db, employee.user.id)
    db.commit()
    db.refresh(employee)
    return employee


async def reset_password(db: Session, employee: Employee, password: str, *, env=None) -> None:
    user = employee.user
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    password_hash = await hash_password_remote(env, password)
    if has_binding(env):
        await d1_batch(
            env,
            [
                (
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    [password_hash, utcnow_text(), user.id],
                ),
                ("DELETE FROM user_sessions WHERE user_id = ?", [user.id]),
            ],
        )
        return

    user.password_hash = password_hash
    await _revoke_sessions(db, user.id)
    db.commit()


def lookup_employee(db: Session, employee_code: str) -> Employee:
    employee = db.scalar(
        select(Employee).where(
            func.lower(Employee.employee_code) == employee_code.strip().lower(),
            Employee.is_active.is_(True),
        )
    )
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active employee found with that ID",
        )
    return employee


def list_availability(
    db: Session, employee_id: int, *, start: date, end: date
) -> list[Availability]:
    stmt = (
        select(Availability)
        .where(
            Availability.employee_id == employee_id,
            Availability.date >= start,
            Availability.date <= end,
        )
        .order_by(Availability.date)
    )
    return list(db.scalars(stmt))


async def add_availability(
    db: Session,
    employee_id: int,
    *,
    start: date,
    end: date,
    kind: AvailabilityKind,
    note: str | None,
    created_by: int | None,
    env=None,
) -> list[Availability]:
    if has_binding(env):
        now = utcnow_text()
        values: list[tuple] = []
        current = start
        while current <= end:
            values.append((employee_id, current.isoformat(), kind.value, note, created_by, now))
            current = date.fromordinal(current.toordinal() + 1)

        statements = multi_row_insert(
            "availability",
            ["employee_id", "date", "kind", "note", "created_by", "created_at"],
            values,
        )
        upsert = (
            " ON CONFLICT (employee_id, date) DO UPDATE SET "
            "kind = excluded.kind, note = excluded.note, created_by = excluded.created_by"
        )
        await d1_batch(env, [(sql + upsert, params) for sql, params in statements])
        db.expire_all()
        return list_availability(db, employee_id, start=start, end=end)

    existing_by_date = {
        record.date: record
        for record in db.scalars(
            select(Availability).where(
                Availability.employee_id == employee_id,
                Availability.date >= start,
                Availability.date <= end,
            )
        )
    }
    created: list[Availability] = []
    current = start
    while current <= end:
        existing = existing_by_date.get(current)
        if existing:
            existing.kind = kind
            existing.note = note
            existing.created_by = created_by
            created.append(existing)
        else:
            record = Availability(
                employee_id=employee_id,
                date=current,
                kind=kind,
                note=note,
                created_by=created_by,
            )
            db.add(record)
            created.append(record)
        current = date.fromordinal(current.toordinal() + 1)
    db.commit()
    for record in created:
        db.refresh(record)
    return created


async def delete_availability(
    db: Session, employee_id: int, availability_id: int, *, env=None
) -> None:
    record = db.get(Availability, availability_id)
    if record is None or record.employee_id != employee_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Availability entry not found"
        )
    if has_binding(env):
        await d1_batch(
            env,
            [
                (
                    "DELETE FROM availability WHERE id = ? AND employee_id = ?",
                    [availability_id, employee_id],
                )
            ],
        )
        return
    db.delete(record)
    db.commit()
