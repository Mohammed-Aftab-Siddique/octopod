from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import AdminUser, DbSession, csrf_protect
from app.api.utils import client_ip, request_env
from app.core.security import rate_limiter
from app.models.availability import Availability
from app.models.employee import Employee
from app.schemas.availability import AvailabilityCreate, AvailabilityOut
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeLookupOut,
    EmployeeOut,
    EmployeeUpdate,
    PasswordResetRequest,
)
from app.services import employees as service

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    db: DbSession,
    admin: AdminUser,
    include_inactive: bool = True,
) -> list[Employee]:
    return service.list_employees(db, include_inactive=include_inactive)


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: EmployeeCreate,
    request: Request,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> Employee:
    return await service.create_employee(db, payload, admin.id, env=request_env(request))


@router.get("/lookup", response_model=EmployeeLookupOut)
async def lookup_employee(employee_code: str, request: Request, db: DbSession) -> EmployeeLookupOut:
    await rate_limiter.check(
        f"lookup:{client_ip(request)}",
        limit=30,
        window_seconds=60,
        env=request_env(request),
    )
    employee = service.lookup_employee(db, employee_code)
    return EmployeeLookupOut(employee_code=employee.employee_code, full_name=employee.full_name)


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(employee_id: int, db: DbSession, admin: AdminUser) -> Employee:
    return service.get_employee(db, employee_id)


@router.patch("/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    request: Request,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> Employee:
    employee = service.get_employee(db, employee_id)
    return await service.update_employee(db, employee, payload, env=request_env(request))


@router.post("/{employee_id}/deactivate", response_model=EmployeeOut)
async def deactivate_employee(
    employee_id: int,
    request: Request,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> Employee:
    employee = service.get_employee(db, employee_id)
    return await service.deactivate_employee(db, employee, env=request_env(request))


@router.post("/{employee_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    employee_id: int,
    payload: PasswordResetRequest,
    request: Request,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> None:
    employee = service.get_employee(db, employee_id)
    await service.reset_password(db, employee, payload.password, env=request_env(request))


@router.get("/{employee_id}/availability", response_model=list[AvailabilityOut])
async def list_availability(
    employee_id: int,
    db: DbSession,
    admin: AdminUser,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> list[Availability]:
    service.get_employee(db, employee_id)
    start = from_date or (date.today().replace(day=1) - timedelta(days=31))
    end = to_date or (start + timedelta(days=180))
    return service.list_availability(db, employee_id, start=start, end=end)


@router.post(
    "/{employee_id}/availability",
    response_model=list[AvailabilityOut],
    status_code=status.HTTP_201_CREATED,
)
async def add_availability(
    employee_id: int,
    payload: AvailabilityCreate,
    request: Request,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> list[Availability]:
    service.get_employee(db, employee_id)
    return await service.add_availability(
        db,
        employee_id,
        start=payload.start_date,
        end=payload.end_date,
        kind=payload.kind,
        note=payload.note,
        created_by=admin.id,
        env=request_env(request),
    )


@router.delete(
    "/{employee_id}/availability/{availability_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_availability(
    employee_id: int,
    availability_id: int,
    request: Request,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> None:
    await service.delete_availability(db, employee_id, availability_id, env=request_env(request))
