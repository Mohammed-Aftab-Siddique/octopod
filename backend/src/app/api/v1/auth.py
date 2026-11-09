from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import AuthContextDep, DbSession, csrf_protect, get_current_user
from app.api.utils import client_ip
from app.core.config import Settings, get_settings
from app.core.security import rate_limiter
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse
from app.services import auth as service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    max_age = settings.session_ttl_hours * 3600
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest, request: Request, response: Response, db: DbSession
) -> LoginResponse:
    env = request.scope.get("env")
    settings = get_settings(env)
    await rate_limiter.check(
        f"login:{client_ip(request)}:{payload.identifier.lower()}",
        limit=20,
        window_seconds=60,
        env=env,
    )

    user = await service.authenticate(db, payload.identifier, payload.password, env=env)
    raw_token, csrf_token = await service.create_session(db, user, env=env)
    _set_session_cookie(response, raw_token, settings)
    return LoginResponse(user=service.user_out(user), csrf_token=csrf_token)


@router.get("/me", response_model=MeResponse)
async def me(auth: AuthContextDep) -> MeResponse:
    return MeResponse(user=service.user_out(auth.user), csrf_token=auth.session.csrf_token)


@router.post("/logout", dependencies=[Depends(csrf_protect)])
async def logout(
    db: DbSession,
    request: Request,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    env = request.scope.get("env")
    settings = get_settings(env)
    await service.revoke_session(db, request.cookies.get(settings.session_cookie_name), env=env)
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"detail": "Logged out"}
