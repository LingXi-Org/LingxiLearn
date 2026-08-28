"""Native Lingxi workspace API, composed from domain route modules."""

from fastapi import APIRouter

from .workspace_artifact_routes import router as artifact_router
from .workspace_core_routes import router as core_router
from .workspace_skill_routes import router as skill_router

__all__ = ["router"]

router = APIRouter()
for domain_router in (
    core_router,
    artifact_router,
    skill_router,
):
    # Domain routers already own the public /api prefix.
    router.routes.extend(domain_router.routes)

# FastAPI tracks explicit route collection mutations separately.
router._routes_version += 1
