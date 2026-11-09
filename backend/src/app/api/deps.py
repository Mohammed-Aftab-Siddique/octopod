import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.security import token_hash
from app.db.session import get_db
from app.models.user import Role, User, UserSession

DbSession = Annotated[Session, Depends(get_db)]


def _load_session(db: Session, token: str | None) -> UserSession | None:
    if not token:
        return None
    record = db.scalar(
        select(UserSession)
        .options(joinedload(UserSession.user))
        .where(UserSession.token_hash == token_hash(token))
    )
    if record is None:
        return None
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        db.delete(record)
        db.commit()
        return None
    return record


async def _session_record(request: Request, db: DbSession) -> UserSession | None:
    settings = get_settings(request.scope.get("env"))
    token = request.cookies.get(settings.session_cookie_name)
    return _load_session(db, token)


@dataclass
class AuthContext:
    """Resolved once per request and shared by all auth dependencies."""

    session: UserSession
    user: User


async def get_auth_context(
    record: Annotated[UserSession | None, Depends(_session_record)],
) -> AuthContext:
    if record is None or not record.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return AuthContext(session=record, user=record.user)


AuthContextDep = Annotated[AuthContext, Depends(get_auth_context)]


async def get_current_user(auth: AuthContextDep) -> User:
    return auth.user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != Role.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required"
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]


async def csrf_protect(
    auth: AuthContextDep,
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    if not x_csrf_token or not secrets.compare_digest(x_csrf_token, auth.session.csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
