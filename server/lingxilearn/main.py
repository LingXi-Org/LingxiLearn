"""FastAPI application.

Serves the API under ``/api`` and, when a production web build is present,
the single-page app from ``/``.  One process, one port — the fewest moving
parts a judge or a teaching assistant has to get right to see it work.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .config import REPO_ROOT, get_settings
from .service import Service

logger = logging.getLogger(__name__)

WEB_DIST = Path(os.environ.get("LINGXILEARN_WEB_DIST", REPO_ROOT / "web" / "out"))


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    settings.var_dir.mkdir(parents=True, exist_ok=True)

    service = Service(settings)
    # Convenience for the zero-setup SQLite path; Postgres deployments run
    # `alembic upgrade head` in a one-shot migrate step before the app starts.
    if settings.database_url.startswith("sqlite"):
        await service.db.create_all()
    await service.startup()
    app.state.service = service
    try:
        yield
    finally:
        await service.shutdown()


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

    if WEB_DIST.exists():
        app.mount("/_next", StaticFiles(directory=WEB_DIST / "_next"), name="next-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):  # noqa: ANN202
            candidate = WEB_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            page = WEB_DIST / full_path / "index.html"
            if page.is_file():
                return FileResponse(page)
            return FileResponse(WEB_DIST / "index.html")

    return app


app = create_app()
