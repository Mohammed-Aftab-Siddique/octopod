from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import AdminUser, CurrentUser, DbSession, csrf_protect
from app.api.utils import request_env
from app.models.reference import Holiday, ShiftStatus
from app.schemas.reference import (
    HolidayCreate,
    HolidayOut,
    RosterSettingsOut,
    RosterSettingsUpdate,
    ShiftStatusOut,
    StaffingRequirementOut,
    StaffingRequirementsPut,
)
from app.services import reference as service

router = APIRouter(prefix="/reference", tags=["reference"])


@router.get("/roster-settings", response_model=RosterSettingsOut)
async def get_roster_settings(db: DbSession, admin: AdminUser) -> RosterSettingsOut:
    return service.get_roster_settings(db)


@router.put("/roster-settings", response_model=RosterSettingsOut)
async def put_roster_settings(
    payload: RosterSettingsUpdate,
    request: Request,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> RosterSettingsOut:
    return await service.save_roster_settings(db, payload, env=request_env(request))


@router.get("/shift-statuses", response_model=list[ShiftStatusOut])
async def list_statuses(db: DbSession, user: CurrentUser) -> list[ShiftStatus]:
    return service.list_statuses(db)


@router.get("/staffing-requirements", response_model=list[StaffingRequirementOut])
async def list_requirements(db: DbSession, admin: AdminUser) -> list[StaffingRequirementOut]:
    return service.list_requirements(db)


@router.put("/staffing-requirements", response_model=list[StaffingRequirementOut])
async def put_requirements(
    payload: StaffingRequirementsPut,
    request: Request,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> list[StaffingRequirementOut]:
    return await service.replace_requirements(db, payload, env=request_env(request))


@router.get("/holidays", response_model=list[HolidayOut])
async def list_holidays(
    db: DbSession,
    user: CurrentUser,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
) -> list[Holiday]:
    return service.list_holidays(db, year, month)


@router.post("/holidays", response_model=HolidayOut, status_code=status.HTTP_201_CREATED)
async def create_holiday(
    payload: HolidayCreate,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> Holiday:
    return service.create_holiday(db, payload)


@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(
    holiday_id: int,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> None:
    service.delete_holiday(db, holiday_id)
