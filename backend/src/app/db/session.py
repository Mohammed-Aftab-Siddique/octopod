from collections.abc import AsyncGenerator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# Counts SQL statements per request. D1 batch calls bypass SQLAlchemy and should
# be counted as one query by the caller. The Workers Free plan allows 50 queries
# per invocation; 40 leaves headroom for the auth/session lookups.
query_count: ContextVar[int] = ContextVar("query_count", default=0)
QUERY_BUDGET = 40

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None
_engine_has_binding = False


def _count_statement(*_args, **_kwargs) -> None:
    query_count.set(query_count.get() + 1)


def reset_query_count() -> None:
    query_count.set(0)


def _create_engine(binding=None) -> Engine:
    if binding is not None:
        from sqlalchemy_cloudflare_d1 import create_engine_from_binding

        engine = create_engine_from_binding(binding)
    else:
        settings = get_settings()
        connect_args = (
            {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        )
        engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            future=True,
        )
    event.listen(engine, "before_cursor_execute", _count_statement)
    return engine


def get_engine(binding=None) -> Engine:
    """Return the isolate-local engine, creating it from the binding if needed."""

    global _engine, _SessionLocal, _engine_has_binding
    if _engine is None or (binding is not None and not _engine_has_binding):
        _engine = _create_engine(binding)
        _engine_has_binding = binding is not None
        _SessionLocal = sessionmaker(
            bind=_engine,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
    return _engine


def get_sessionmaker(binding=None) -> sessionmaker[Session]:
    global _SessionLocal
    get_engine(binding)
    assert _SessionLocal is not None
    return _SessionLocal


def reset_engine() -> None:
    """Dispose the cached engine. Used by tests that swap databases."""

    global _engine, _SessionLocal, _engine_has_binding
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
    _engine_has_binding = False


@contextmanager
def session_scope(binding=None) -> Iterator[Session]:
    """Synchronous session context used by local scripts and the lifespan hook."""

    with get_sessionmaker(binding)() as db:
        yield db


async def get_db(request: Request) -> AsyncGenerator[Session, None]:
    """Request-scoped SQLAlchemy session.

    The dependency is async so Starlette never schedules it on a thread pool;
    Pyodide is single-threaded and the D1 dialect bridges sync SQLAlchemy calls
    internally.
    """

    env = request.scope.get("env")
    binding = getattr(env, "DB", None) if env is not None else None
    with get_sessionmaker(binding)() as db:
        yield db
