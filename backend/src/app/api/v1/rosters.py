from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.deps import AdminUser, CurrentUser, DbSession, csrf_protect
from app.api.utils import request_env
from app.models.roster import RosterPeriod, RosterStatus
from app.models.user import Role
from app.schemas.roster import (
    AssignmentsPatch,
    GenerationResult,
    RosterCreate,
    RosterGrid,
    RosterSummary,
)
from app.services import rosters as service
from app.services.export import render_png_remote
from app.services.generation import generate_roster

router = APIRouter(tags=["rosters"])


@router.get("/rosters", response_model=list[RosterSummary])
async def list_rosters(
    db: DbSession,
    admin: AdminUser,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
) -> list[RosterPeriod]:
    return service.list_periods(db, year, month)


@router.post("/rosters", response_model=RosterGrid, status_code=status.HTTP_201_CREATED)
async def create_roster(
    payload: RosterCreate,
    request: Request,
    response: Response,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> RosterGrid:
    period, created = await service.get_or_create_draft(
        db, payload.year, payload.month, admin.id, env=request_env(request)
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return service.build_grid(db, period)


@router.get("/rosters/{roster_id}", response_model=RosterGrid)
async def get_roster(roster_id: int, db: DbSession, admin: AdminUser) -> RosterGrid:
    period = service.get_period(db, roster_id)
    return service.build_grid(db, period)


@router.patch("/rosters/{roster_id}/assignments", response_model=RosterGrid)
async def patch_assignments(
    roster_id: int,
    payload: AssignmentsPatch,
    request: Request,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> RosterGrid:
    period = service.get_period(db, roster_id)
    return await service.patch_assignments(
        db, period, payload.assignments, env=request_env(request)
    )


@router.post("/rosters/{roster_id}/generate", response_model=GenerationResult)
async def generate(
    roster_id: int,
    request: Request,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> GenerationResult:
    env = request_env(request)
    period = service.get_period(db, roster_id)
    if period.status != RosterStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Only draft rosters can be generated"
        )
    rows, shortages, warnings = generate_roster(db, period)
    await service.write_generation_result(
        db,
        period,
        [(row["employee_id"], row["date"], row["status_code"]) for row in rows],
        user_id=admin.id,
        shortages=shortages,
        warnings=warnings,
        env=env,
    )
    period = service.get_period(db, roster_id)
    return GenerationResult(
        roster=service.build_grid(db, period), shortages=shortages, warnings=warnings
    )


@router.post("/rosters/{roster_id}/publish", response_model=RosterGrid)
async def publish(
    roster_id: int,
    request: Request,
    db: DbSession,
    admin: AdminUser,
    _csrf: Annotated[None, Depends(csrf_protect)],
) -> RosterGrid:
    period = service.get_period(db, roster_id)
    period = await service.publish_period(db, period, admin.id, env=request_env(request))
    return service.build_grid(db, period)


@router.get("/rosters/{roster_id}/export.png")
async def export_roster(
    roster_id: int,
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> Response:
    period = service.get_period(db, roster_id)
    if user.role != Role.admin and period.status != RosterStatus.published:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only published rosters can be exported by employees",
        )
    grid = service.build_grid(db, period)
    png = await render_png_remote(request_env(request), grid)
    filename = f"roster-{period.year}-{period.month:02d}-v{period.version}.png"
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/me/roster", response_model=RosterGrid)
async def my_roster(
    db: DbSession,
    user: CurrentUser,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
) -> RosterGrid:
    period = service.get_published_period(db, year, month)
    if period is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No published roster available for that month",
        )
    return service.build_grid(db, period)
