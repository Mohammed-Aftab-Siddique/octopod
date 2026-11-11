import calendar
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.d1 import d1_batch, has_binding, multi_row_insert
from app.models.reference import Holiday, ShiftStatus, StaffingRequirement
from app.schemas.reference import (
    HolidayCreate,
    StaffingRequirementOut,
    StaffingRequirementsPut,
)


def list_statuses(db: Session) -> list[ShiftStatus]:
    return list(db.scalars(select(ShiftStatus).order_by(ShiftStatus.sort_order)))


def list_requirements(db: Session) -> list[StaffingRequirementOut]:
    rows = db.execute(
        select(StaffingRequirement, ShiftStatus).join(
            ShiftStatus, StaffingRequirement.status_id == ShiftStatus.id
        )
    ).all()
    return [
        StaffingRequirementOut(
            status_code=shift_status.code,
            required_count=requirement.required_count,
        )
        for requirement, shift_status in rows
    ]


async def replace_requirements(
    db: Session, payload: StaffingRequirementsPut, *, env=None
) -> list[StaffingRequirementOut]:
    statuses = {item.code: item for item in db.scalars(select(ShiftStatus))}
    seen: set[str] = set()
    for requirement in payload.requirements:
        code = requirement.status_code.upper()
        if code not in statuses or not statuses[code].is_working:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status {requirement.status_code} is not a working shift",
            )
        if code in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate shift requirement",
            )
        seen.add(code)

    if has_binding(env):
        values = [
            (
                statuses[requirement.status_code.upper()].id,
                requirement.required_count,
            )
            for requirement in payload.requirements
        ]
        statements: list[tuple[str, list]] = [("DELETE FROM staffing_requirements", [])]
        statements.extend(
            multi_row_insert(
                "staffing_requirements",
                ["status_id", "required_count"],
                values,
            )
        )
        await d1_batch(env, statements)
        db.expire_all()
        return list_requirements(db)

    db.query(StaffingRequirement).delete()
    for requirement in payload.requirements:
        db.add(
            StaffingRequirement(
                status_id=statuses[requirement.status_code.upper()].id,
                required_count=requirement.required_count,
            )
        )
    db.commit()
    return list_requirements(db)


def list_holidays(db: Session, year: int, month: int) -> list[Holiday]:
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    return list(
        db.scalars(
            select(Holiday)
            .where(Holiday.date >= first, Holiday.date <= last)
            .order_by(Holiday.date)
        )
    )


def create_holiday(db: Session, payload: HolidayCreate) -> Holiday:
    holiday = Holiday(date=payload.date, label=payload.label)
    db.add(holiday)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A holiday already exists on that date"
        ) from exc
    db.refresh(holiday)
    return holiday


def delete_holiday(db: Session, holiday_id: int) -> None:
    holiday = db.get(Holiday, holiday_id)
    if holiday is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")
    db.delete(holiday)
    db.commit()
