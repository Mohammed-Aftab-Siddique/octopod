from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    new_token,
    token_hash,
    verify_password_remote,
)
from app.db.d1 import d1_batch, has_binding, utcnow_text
from app.models.employee import Employee
from app.models.user import User, UserSession
from app.schemas.auth import UserOut


def user_out(user: User) -> UserOut:
    employee = user.employee
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        employee_id=user.employee_id,
        full_name=employee.full_name
        if employee
        else ("Administrator" if user.role.value == "admin" else None),
        employee_code=employee.employee_code if employee else None,
    )


def find_user(db: Session, identifier: str) -> User | None:
    value = identifier.strip()
    if "@" in value:
        return db.scalar(select(User).where(func.lower(User.email) == value.lower()))
    employee = db.scalar(
        select(Employee).where(func.lower(Employee.employee_code) == value.lower())
    )
    if employee is None:
        return None
    return db.scalar(select(User).where(User.employee_id == employee.id))


async def authenticate(db: Session, identifier: str, password: str, *, env=None) -> User:
    user = find_user(db, identifier)
    if (
        user is None
        or not user.is_active
        or not await verify_password_remote(env, password, user.password_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


async def create_session(db: Session, user: User, *, env=None) -> tuple[str, str]:
    """Create a session and return ``(raw_token, csrf_token)``.

    On D1 the expired-session prune and the insert are sent as one atomic batch.
    """

    ttl = get_settings(env).session_ttl_hours
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=ttl)

    raw_token = new_token()
    csrf_token = new_token()

    if has_binding(env):
        await d1_batch(
            env,
            [
                (
                    "DELETE FROM user_sessions WHERE user_id = ? AND expires_at < ?",
                    [user.id, utcnow_text()],
                ),
                (
                    "INSERT INTO user_sessions "
                    "(token_hash, csrf_token, user_id, expires_at, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [
                        token_hash(raw_token),
                        csrf_token,
                        user.id,
                        expires_at.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S.%f"),
                        now.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S.%f"),
                    ],
                ),
            ],
        )
    else:
        # Opportunistically prune this user's expired sessions so the table does
        # not grow without bound on long-lived installations.
        for expired in db.scalars(
            select(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at < now)
        ):
            db.delete(expired)

        db.add(
            UserSession(
                token_hash=token_hash(raw_token),
                csrf_token=csrf_token,
                user_id=user.id,
                expires_at=expires_at,
            )
        )
        db.commit()

    return raw_token, csrf_token


async def revoke_session(db: Session, raw_token: str | None, *, env=None) -> None:
    if not raw_token:
        return
    if has_binding(env):
        await d1_batch(
            env,
            [
                (
                    "DELETE FROM user_sessions WHERE token_hash = ?",
                    [token_hash(raw_token)],
                )
            ],
        )
        return
    record = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(raw_token)))
    if record is not None:
        db.delete(record)
        db.commit()
