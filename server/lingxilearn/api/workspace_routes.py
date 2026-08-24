"""Native Lingxi workspace API, composed from domain route modules."""

from fastapi import APIRouter

from .workspace_core_routes import router as core_router
from .workspace_file_routes import router as file_router
from .workspace_knowledge_routes import router as knowledge_router
from .workspace_log_routes import router as log_router
from .workspace_route_shared import _utc_datetime
from .workspace_skill_routes import router as skill_router
from .workspace_table_routes import router as table_router

__all__ = ["_utc_datetime", "router"]

router = APIRouter()
for domain_router in (
    core_router,
    file_router,
    table_router,
    knowledge_router,
    skill_router,
    log_router,
):
    # Preserve concrete APIRoute objects and registration order for compatibility
    # with route-introspection tests and tooling. Domain routers already own /api.
    router.routes.extend(domain_router.routes)

# FastAPI 0.135 tracks mutations separately from Starlette's public ``routes``
# collection so a subsequently included router can be materialized lazily.
# The aggregation above is one logical route mutation.
router._routes_version += 1
