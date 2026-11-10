from __future__ import annotations

import calendar
import json
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.d1 import d1_batch, has_binding, multi_row_insert, utcnow_text
from app.models.employee import Employee
from app.models.reference import Holiday, ShiftStatus
from app.models.roster import (
    GenerationRun,
    RosterAssignment,
    RosterPeriod,
    RosterStatus,
)
from app.schemas.roster import AssignmentUpdate, RosterGrid

if TYPE_CHECKING:
    from app.services.generation import ShortageRow

WEEKDAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

UPSERT_ASSIGNMENT = (
    "INSERT INTO roster_assignments "
    "(roster_period_id, employee_id, date, status_id, note, updated_at) "
    "VALUES (?, ?, ?, ?, ?, ?) "
    "ON CONFLICT (roster_period_id, employee_id, date) DO UPDATE SET "
    "status_id = excluded.status_id, note = excluded.note, updated_at = excluded.updated_at"
)


def _batch_changes(result) -> int | None:
    try:
        meta = getattr(result, "meta", None)
        if meta is None:
            meta = result["meta"]
        changes = getattr(meta, "changes", None)
        if changes is None:
            changes = meta["changes"]
        return int(changes)
    except Exception:  # pragma: no cover - depends on the D1 result object
        return None


def get_period(db: Session, period_id: int) -> RosterPeriod:
    period = db.get(RosterPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roster not found")
    return period


def list_periods(db: Session, year: int, month: int) -> list[RosterPeriod]:
    stmt = (
        select(RosterPeriod)
        .where(RosterPeriod.year == year, RosterPeriod.month == month)
        .order_by(RosterPeriod.version.desc())
    )
    return list(db.scalars(stmt))


async def get_or_create_draft(
    db: Session, year: int, month: int, user_id: int | None, *, env=None
) -> tuple[RosterPeriod, bool]:
    """Return ``(draft, created)`` for the requested month.

    Creating a draft is idempotent: repeated calls return the same period and
    report ``created=False`` so the API can answer 200 instead of 201.
    """

    existing = db.scalar(
        select(RosterPeriod).where(
            RosterPeriod.year == year,
            RosterPeriod.month == month,
            RosterPeriod.status == RosterStatus.draft,
        )
    )
    if existing:
        return existing, False

    max_version = (
        db.scalar(
            select(func.max(RosterPeriod.version)).where(
                RosterPeriod.year == year, RosterPeriod.month == month
            )
        )
        or 0
    )

    if has_binding(env):
        now = utcnow_text()
        # The partial unique index guarantees a single draft. ON CONFLICT DO
        # NOTHING makes the read/insert race safe without a transaction.
        await d1_batch(
            env,
            [
                (
                    "INSERT INTO roster_periods "
                    "(year, month, version, status, created_by, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'draft', ?, ?, ?) ON CONFLICT DO NOTHING",
                    [year, month, max_version + 1, user_id, now, now],
                )
            ],
        )
        db.expire_all()
        period = db.scalar(
            select(RosterPeriod).where(
                RosterPeriod.year == year,
                RosterPeriod.month == month,
                RosterPeriod.status == RosterStatus.draft,
            )
        )
        if period is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Draft roster could not be created",
            )
        return period, True

    period = RosterPeriod(
        year=year,
        month=month,
        version=max_version + 1,
        status=RosterStatus.draft,
        created_by=user_id,
    )
    db.add(period)
    try:
        db.commit()
    except IntegrityError:
        # Another request created the month's draft between our read and
        # write. The partial unique index guarantees only one exists, so
        # return the winner instead of failing.
        db.rollback()
        existing = db.scalar(
            select(RosterPeriod).where(
                RosterPeriod.year == year,
                RosterPeriod.month == month,
                RosterPeriod.status == RosterStatus.draft,
            )
        )
        if existing is None:
            raise
        return existing, False
    db.refresh(period)
    return period, True


async def delete_period(db: Session, period: RosterPeriod, *, env=None) -> None:
    """Permanently delete a roster version and its assignments/runs."""

    if has_binding(env):
        await d1_batch(
            env,
            [
                (
                    "DELETE FROM roster_assignments WHERE roster_period_id = ?",
                    [period.id],
                ),
                (
                    "DELETE FROM generation_runs WHERE roster_period_id = ?",
                    [period.id],
                ),
                ("DELETE FROM roster_periods WHERE id = ?", [period.id]),
            ],
        )
        db.expire_all()
        return

    db.delete(period)
    db.commit()


def get_published_period(db: Session, year: int, month: int) -> RosterPeriod | None:
    return db.scalar(
        select(RosterPeriod).where(
            RosterPeriod.year == year,
            RosterPeriod.month == month,
            RosterPeriod.status == RosterStatus.published,
        )
    )


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def build_grid(db: Session, period: RosterPeriod) -> RosterGrid:
    first, last = month_bounds(period.year, period.month)
    holidays = {
        holiday.date: holiday.label
        for holiday in db.scalars(
            select(Holiday).where(Holiday.date >= first, Holiday.date <= last)
        )
    }

    days = []
    for ordinal in range(first.toordinal(), last.toordinal() + 1):
        current = date.fromordinal(ordinal)
        days.append(
            {
                "date": current,
                "day": current.day,
                "weekday": current.weekday(),
                "weekday_label": WEEKDAY_LABELS[current.weekday()],
                "is_weekend": current.weekday() >= 5,
                "holiday": holidays.get(current),
            }
        )

    assignments_by_period = list(
        db.scalars(select(RosterAssignment).where(RosterAssignment.roster_period_id == period.id))
    )
    assigned_employee_ids = {assignment.employee_id for assignment in assignments_by_period}
    stmt = select(Employee).order_by(Employee.full_name)
    if period.status == RosterStatus.draft:
        # Drafts cover every currently active employee, plus anyone already
        # assigned (for example an employee deactivated mid-month).
        if assigned_employee_ids:
            stmt = stmt.where(
                (Employee.is_active.is_(True)) | (Employee.id.in_(assigned_employee_ids))
            )
        else:
            stmt = stmt.where(Employee.is_active.is_(True))
    else:
        # Published and archived versions show exactly the employees that
        # belong to that version, not later hires.
        if assigned_employee_ids:
            stmt = stmt.where(Employee.id.in_(assigned_employee_ids))
        else:
            stmt = stmt.where(Employee.id.is_(None))
    employees = list(db.scalars(stmt))

    statuses = list(db.scalars(select(ShiftStatus).order_by(ShiftStatus.sort_order)))
    status_by_id = {item.id: item for item in statuses}

    assignments = [
        {
            "employee_id": assignment.employee_id,
            "date": assignment.date,
            "status_code": status_by_id[assignment.status_id].code,
            "note": assignment.note,
        }
        for assignment in assignments_by_period
        if assignment.status_id in status_by_id
    ]

    return RosterGrid(
        id=period.id,
        year=period.year,
        month=period.month,
        version=period.version,
        status=period.status,
        days=days,
        employees=[
            {
                "id": employee.id,
                "employee_code": employee.employee_code,
                "full_name": employee.full_name,
            }
            for employee in employees
        ],
        statuses=statuses,
        assignments=assignments,
        updated_at=period.updated_at,
        published_at=period.published_at,
    )


async def patch_assignments(
    db: Session, period: RosterPeriod, updates: list[AssignmentUpdate], *, env=None
) -> RosterGrid:
    if period.status != RosterStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft rosters can be edited",
        )
    first, last = month_bounds(period.year, period.month)
    status_by_code = {item.code.upper(): item for item in db.scalars(select(ShiftStatus))}
    seen: set[tuple[int, date]] = set()
    employee_ids = {update.employee_id for update in updates}
    existing_employees = set(db.scalars(select(Employee.id).where(Employee.id.in_(employee_ids))))
    for update in updates:
        key = (update.employee_id, update.date)
        if key in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate employee/date entries in request",
            )
        seen.add(key)
        if not (first <= update.date <= last):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Date {update.date} is outside the roster month",
            )
        if update.status_code.upper() not in status_by_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown status code {update.status_code}",
            )
        if update.employee_id not in existing_employees:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    now = utcnow_text()

    if has_binding(env):
        statements: list[tuple[str, list]] = [
            (
                UPSERT_ASSIGNMENT,
                [
                    period.id,
                    update.employee_id,
                    update.date.isoformat(),
                    status_by_code[update.status_code.upper()].id,
                    update.note,
                    now,
                ],
            )
            for update in updates
        ]
        statements.append(
            ("UPDATE roster_periods SET updated_at = ? WHERE id = ?", [now, period.id])
        )
        await d1_batch(env, statements)
        db.expire_all()
        return build_grid(db, get_period(db, period.id))

    assignments = {
        (assignment.employee_id, assignment.date): assignment
        for assignment in db.scalars(
            select(RosterAssignment).where(RosterAssignment.roster_period_id == period.id)
        )
    }
    for update in updates:
        shift_status = status_by_code[update.status_code.upper()]
        assignment = assignments.get((update.employee_id, update.date))
        if assignment is None:
            assignment = RosterAssignment(
                roster_period_id=period.id,
                employee_id=update.employee_id,
                date=update.date,
                status_id=shift_status.id,
                note=update.note,
            )
            db.add(assignment)
        else:
            assignment.status_id = shift_status.id
            assignment.note = update.note

    period.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(period)
    return build_grid(db, period)


async def replace_assignments(
    db: Session, period: RosterPeriod, rows: list[tuple[int, date, str]], *, env=None
) -> None:
    """Replace all assignments in a draft. Used by the generator."""

    statuses = {item.code: item for item in db.scalars(select(ShiftStatus))}
    now = utcnow_text()

    if has_binding(env):
        values = [
            (period.id, employee_id, assignment_date.isoformat(), statuses[code].id, now)
            for employee_id, assignment_date, code in rows
        ]
        statements: list[tuple[str, list]] = [
            ("DELETE FROM roster_assignments WHERE roster_period_id = ?", [period.id])
        ]
        statements.extend(
            multi_row_insert(
                "roster_assignments",
                ["roster_period_id", "employee_id", "date", "status_id", "updated_at"],
                values,
            )
        )
        statements.append(
            ("UPDATE roster_periods SET updated_at = ? WHERE id = ?", [now, period.id])
        )
        await d1_batch(env, statements)
        db.expire_all()
        return

    db.query(RosterAssignment).filter(RosterAssignment.roster_period_id == period.id).delete()
    for employee_id, assignment_date, code in rows:
        shift_status = statuses[code]
        db.add(
            RosterAssignment(
                roster_period_id=period.id,
                employee_id=employee_id,
                date=assignment_date,
                status_id=shift_status.id,
            )
        )
    period.updated_at = datetime.now(UTC)


async def write_generation_result(
    db: Session,
    period: RosterPeriod,
    rows: list[tuple[int, date, str]],
    *,
    user_id: int | None,
    shortages: list[ShortageRow],
    warnings: list[str],
    env=None,
) -> None:
    """Write assignments, the period timestamp, and the generation run.

    On D1 this is a single atomic batch so a partially generated roster can never
    be observed.
    """

    statuses = {item.code: item for item in db.scalars(select(ShiftStatus))}
    now = utcnow_text()
    run_status = "partial" if shortages else "succeeded"

    if has_binding(env):
        values = [
            (period.id, employee_id, assignment_date.isoformat(), statuses[code].id, now)
            for employee_id, assignment_date, code in rows
        ]
        statements: list[tuple[str, list]] = [
            ("DELETE FROM roster_assignments WHERE roster_period_id = ?", [period.id])
        ]
        statements.extend(
            multi_row_insert(
                "roster_assignments",
                ["roster_period_id", "employee_id", "date", "status_id", "updated_at"],
                values,
            )
        )
        statements.append(
            ("UPDATE roster_periods SET updated_at = ? WHERE id = ?", [now, period.id])
        )
        statements.append(
            (
                "INSERT INTO generation_runs "
                "(roster_period_id, created_by, created_at, status, shortages, warnings) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    period.id,
                    user_id,
                    now,
                    run_status,
                    json.dumps(shortages),
                    json.dumps(warnings),
                ],
            )
        )
        await d1_batch(env, statements)
        db.expire_all()
        return

    await replace_assignments(db, period, rows)
    await record_generation_run(db, period, user_id=user_id, shortages=shortages, warnings=warnings)


async def publish_period(
    db: Session, period: RosterPeriod, user_id: int, *, env=None
) -> RosterPeriod:
    if period.status != RosterStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft rosters can be published",
        )
    count = db.scalar(
        select(func.count(RosterAssignment.id)).where(
            RosterAssignment.roster_period_id == period.id
        )
    )
    if not count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot publish an empty roster",
        )

    if has_binding(env):
        now = utcnow_text()
        results = await d1_batch(
            env,
            [
                (
                    "UPDATE roster_periods SET status = 'archived', updated_at = ? "
                    "WHERE year = ? AND month = ? AND status = 'published' AND id != ?",
                    [now, period.year, period.month, period.id],
                ),
                (
                    "UPDATE roster_periods SET status = 'published', published_at = ?, "
                    "published_by = ?, updated_at = ? WHERE id = ? AND status = 'draft'",
                    [now, user_id, now, period.id],
                ),
            ],
        )
        changes = _batch_changes(results[1]) if len(results) > 1 else None
        if changes == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft rosters can be published",
            )
        db.expire_all()
        return get_period(db, period.id)

    previous = get_published_period(db, period.year, period.month)
    if previous and previous.id != period.id:
        previous.status = RosterStatus.archived
    period.status = RosterStatus.published
    period.published_at = datetime.now(UTC)
    period.published_by = user_id
    db.commit()
    db.refresh(period)
    return period


async def record_generation_run(
    db: Session,
    period: RosterPeriod,
    *,
    user_id: int | None,
    shortages: list[ShortageRow],
    warnings: list[str],
    env=None,
) -> GenerationRun:
    run_status = "partial" if shortages else "succeeded"

    if has_binding(env):
        await d1_batch(
            env,
            [
                (
                    "INSERT INTO generation_runs "
                    "(roster_period_id, created_by, created_at, status, shortages, warnings) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        period.id,
                        user_id,
                        utcnow_text(),
                        run_status,
                        json.dumps(shortages),
                        json.dumps(warnings),
                    ],
                )
            ],
        )
        db.expire_all()
        return db.scalar(
            select(GenerationRun)
            .where(GenerationRun.roster_period_id == period.id)
            .order_by(GenerationRun.id.desc())
        )

    run = GenerationRun(
        roster_period_id=period.id,
        created_by=user_id,
        status=run_status,
        shortages=shortages,
        warnings=warnings,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
