"""LingxiLearn FastAPI API and identity BFF proxy.

The browser UI is served by the native Next standalone process. FastAPI owns
only API/auth routes; keeping HTML out of this process prevents removed
workflow editor URLs from becoming reachable.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .api.agent_events import router as agent_events_router
from .api.agent_interactions import router as agent_interactions_router
from .api.agent_tasks import router as agent_tasks_router
from .api.artifacts import router as artifacts_router
from .api.catalog import router as catalog_router
from .api.health import router as health_router
from .api.internal_runtime import router as internal_runtime_router
from .api.workspace_routes import router as workspace_router
from .application import ApplicationServices
from .auth import build_authenticator
from .config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    settings = get_settings()
    settings.validate_runtime()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    settings.var_dir.mkdir(parents=True, exist_ok=True)

    services = ApplicationServices(settings)
    # Build the verifier before opening graph/database resources so a strict
    # production configuration fails fast and cleanly.
    identity = await asyncio.to_thread(build_authenticator, settings)
    # The LingxiIdentity SDK client is intentionally lazy and only exposes
    # the identity-specific helpers.  The generic auth proxy needs the full
    # httpx request interface for forwarding arbitrary methods and paths.
    proxy_client = httpx.AsyncClient(
        timeout=settings.identity_bff_timeout,
        follow_redirects=False,
    )
    await services.startup()
    app.state.identity = identity
    app.state.identity_proxy_client = proxy_client
    app.state.services = services
    try:
        yield
    finally:
        await services.shutdown()
        await identity.aclose()
        await proxy_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="LingxiLearn",
        version="1.0.0",
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
    app.include_router(agent_interactions_router)
    app.include_router(agent_events_router)
    app.include_router(agent_tasks_router)
    app.include_router(artifacts_router)
    app.include_router(health_router)
    app.include_router(catalog_router)
    app.include_router(internal_runtime_router)
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
        client = getattr(request.app.state, "identity_proxy_client", None)
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
        # Preserve redirect and cache semantics from the BFF. In particular,
        # the callback's Location must remain a browser navigation and must not
        # be replaced by a JSON response from this proxy.
        for header in ("location", "cache-control", "vary", "www-authenticate"):
            if value := upstream_response.headers.get(header):
                response.headers[header] = value
        # Starlette combines duplicate headers in some response paths; append
        # each Set-Cookie value separately so state/session cookies retain their
        # attributes and are not collapsed into one invalid cookie string.
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
