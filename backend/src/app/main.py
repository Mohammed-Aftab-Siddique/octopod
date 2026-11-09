import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Import models so metadata is populated before create_all.
import app.models  # noqa: F401,E402
from app.api.v1 import api_router
from app.core.config import get_settings, settings_from_env
from app.db.base import Base
from app.db.session import (
    QUERY_BUDGET,
    get_engine,
    get_sessionmaker,
    query_count,
    reset_query_count,
)

logger = logging.getLogger("octopod")

ALLOWED_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
ALLOWED_HEADERS = "Content-Type, X-CSRF-Token"
DEFAULT_SECRET = "dev-secret-change-me"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Use non-caching settings here: on Workers the request-scoped env is not
    # available during lifespan, and caching defaults would hide real vars.
    settings = settings_from_env(None)

    if settings.environment == "production" and settings.secret_key in ("", DEFAULT_SECRET):
        raise RuntimeError("SECRET_KEY must be set in production")

    if settings.auto_create_tables:
        Base.metadata.create_all(bind=get_engine())
    if settings.seed_demo:
        from app.services.seed import seed_demo

        with get_sessionmaker()() as db:
            await seed_demo(db)
    yield


class SettingsCORSMiddleware:
    """CORS driven by the request's env rather than import-time settings.

    Production is same-origin; the allow-list mainly serves the Vite dev server.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings(scope.get("env"))
        origin = Headers(scope=scope).get("origin")
        allowed = bool(origin) and origin in settings.origins

        if not allowed:
            await self.app(scope, receive, send)
            return

        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": ALLOWED_METHODS,
            "Access-Control-Allow-Headers": ALLOWED_HEADERS,
            "Vary": "Origin",
        }

        if scope["method"] == "OPTIONS":
            response = Response(status_code=204, headers=headers)
            await response(scope, receive, send)
            return

        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start":
                mutable = MutableHeaders(scope=message)
                for name, value in headers.items():
                    mutable[name] = value
            await send(message)

        await self.app(scope, receive, send_with_cors)


app = FastAPI(
    title="Octopod Roster",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(SettingsCORSMiddleware)


@app.middleware("http")
async def query_budget_middleware(request: Request, call_next):
    reset_query_count()
    settings = get_settings(request.scope.get("env"))
    if settings.environment == "production" and settings.secret_key in ("", DEFAULT_SECRET):
        return Response("Server misconfigured: SECRET_KEY is missing", status_code=500)

    response = await call_next(request)
    count = query_count.get()
    response.headers["X-Query-Count"] = str(count)
    if count > QUERY_BUDGET:
        logger.warning(
            "Query budget exceeded: %s %s used %s statements",
            request.method,
            request.url.path,
            count,
        )
    return response


app.include_router(api_router, prefix="/api/v1")
