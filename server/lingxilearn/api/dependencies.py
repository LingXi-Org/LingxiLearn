"""Shared FastAPI dependencies for the HTTP transport layer."""

from fastapi import Depends, HTTPException, Request
from lingxi_identity import Principal  # type: ignore[import-untyped]

from ..application import ApplicationServices
from ..auth import get_principal
from ..learner import LearnerContext


def services_of(request: Request) -> ApplicationServices:
    """Return the application composition root attached during startup."""

    services: ApplicationServices | None = getattr(request.app.state, "services", None)
    if services is None:
        raise HTTPException(status_code=503, detail="service_unavailable")
    return services


async def current_learner_context(
    request: Request, principal: Principal = Depends(get_principal)
) -> LearnerContext:
    """Resolve the authenticated principal to its learner-scoped context."""

    services = services_of(request)
    try:
        return await services.learners.get_learner_context(principal)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="invalid_identity") from exc


def not_found() -> HTTPException:
    """Use one response for missing and not-owned persistent resources."""

    return HTTPException(status_code=404, detail="resource_not_found")
