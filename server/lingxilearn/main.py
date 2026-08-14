"""LingxiLearn FastAPI API and identity BFF proxy.

The browser UI is served by the native Next standalone process. FastAPI owns
only API/auth routes; keeping HTML out of this process prevents stale SPA
fallbacks from reviving removed workflow editor URLs.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .api.routes import router
from .api.account_routes import router as account_router
from .api.workspace_routes import router as workspace_router
from .auth import build_authenticator
from .config import get_settings
from .service import Service

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    settings.var_dir.mkdir(parents=True, exist_ok=True)

    service = Service(settings)
    # Build the verifier before opening graph/database resources so a strict
    # production configuration fails fast and cleanly.
    identity = await asyncio.to_thread(build_authenticator, settings)
    # Convenience for the zero-setup SQLite path; this also repairs files
    # created by older local versions in place. Postgres deployments run
    # `alembic upgrade head` in a one-shot migrate step before the app starts.
    if settings.database_url.startswith("sqlite"):
        await service.db.ensure_sqlite_schema()
    await service.startup()
    app.state.identity = identity
    app.state.service = service
    try:
        yield
    finally:
        await service.shutdown()
        await identity.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="LingxiLearn",
        version="0.1.0",
        description="面向高校工科学生的 AI 学习与工程实践助教",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(account_router)
    app.include_router(workspace_router)

    async def proxy_identity(request: Request, upstream_path: str) -> Response:
        upstream = f"{settings.identity_bff_url.rstrip('/')}{upstream_path}"
        if request.url.query:
            upstream = f"{upstream}?{request.url.query}"
        forwarded_headers = {
            name: value
            for name, value in request.headers.items()
            if name.lower()
            in {
                "accept",
                "content-type",
                "cookie",
                "user-agent",
                "x-csrf-token",
                "x-logto-verification-id",
            }
        }
        identity = getattr(request.app.state, "identity", None)
        client = identity.client if identity is not None else None
        if client is None:
            raise HTTPException(status_code=503, detail="identity_provider_unavailable")
        try:
            upstream_response = await client.request(
                request.method,
                upstream,
                headers=forwarded_headers,
                content=await request.body(),
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="identity_provider_unavailable") from exc
        response = Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            media_type=upstream_response.headers.get("content-type"),
        )
        for header in ("location", "cache-control"):
            if value := upstream_response.headers.get(header):
                response.headers[header] = value
        for cookie in upstream_response.headers.get_list("set-cookie"):
            response.headers.append("set-cookie", cookie)
        return response

    @app.api_route(
        "/auth/{identity_path:path}",
        methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        include_in_schema=False,
    )
    async def identity_auth_proxy(request: Request, identity_path: str) -> Response:
        return await proxy_identity(request, f"/auth/{identity_path}")

    @app.api_route(
        "/api/v1/{identity_path:path}",
        methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        include_in_schema=False,
    )
    async def identity_api_proxy(request: Request, identity_path: str) -> Response:
        return await proxy_identity(request, f"/api/v1/{identity_path}")

    return app


app = create_app()
