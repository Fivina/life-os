from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.router import api_router
from app.assistant.tools import ToolRegistry
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.database.session import SessionLocal
from app.skills.registry import SkillRegistry


def create_app(settings_override: Settings | None = None) -> FastAPI:
    settings = settings_override or get_settings()
    configure_logging()
    tool_registry = ToolRegistry()
    skill_registry = SkillRegistry(settings, tool_registry).load()

    app = FastAPI(
        title="Life OS API",
        version=settings.deployment_version,
        description="Private single-user Life OS modular monolith API.",
    )
    app.state.tool_registry = tool_registry
    app.state.skill_registry = skill_registry

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "request_id": request_id}, headers={"X-Request-ID": request_id})

    @app.get("/health", tags=["health"])
    def root_health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "life-os-backend",
            "version": settings.deployment_version,
            "environment": settings.app_env,
        }

    @app.get("/readiness", tags=["health"])
    def root_readiness() -> dict[str, object]:
        with SessionLocal() as db:
            db.execute(text("select 1"))
        auth_ready = settings.development_auth_enabled or bool(settings.supabase_jwt_secret)
        return {
            "status": "ready" if auth_ready else "degraded",
            "database": "reachable",
            "auth": "configured" if auth_ready else "missing",
            "environment": settings.app_env,
        }

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
