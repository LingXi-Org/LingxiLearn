"""Service health endpoint."""

from typing import Any

from fastapi import APIRouter, Request

from ..contracts.rest_models import HealthResponse
from .dependencies import services_of

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> dict[str, Any]:
    services = services_of(request)
    try:
        db_ok = await services.db.ping()
    except Exception:  # noqa: BLE001 - health must answer even when the DB is down
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "brain": services.brain.name if services.brain else "unconfigured",
        "agent": {
            "configured": services.settings.agents_configured,
            "model": services.settings.agent_model,
        },
        "packs": sorted(services.packs),
        "tools": len(services.registry.specs),
    }
