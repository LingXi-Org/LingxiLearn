"""Unauthenticated process liveness and dependency readiness probes."""

from fastapi import APIRouter, Request, Response, status

from ..application import ApplicationServices
from ..contracts.rest_models import LivenessResponse, ReadinessResponse

router = APIRouter()


@router.get("/live", response_model=LivenessResponse)
async def live() -> LivenessResponse:
    """Report only whether the FastAPI process can answer HTTP requests."""

    return LivenessResponse(status="live")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def ready(request: Request, response: Response) -> ReadinessResponse:
    """Report whether application startup completed and the database is usable."""

    services: ApplicationServices | None = getattr(request.app.state, "services", None)
    services_ready = services is not None
    db_ok = False
    try:
        if services is not None:
            db_ok = await services.db.ping()
    except Exception:  # noqa: BLE001 - readiness is communicated as HTTP 503
        db_ok = False
    is_ready = services_ready and db_ok
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        services=services_ready,
        database=db_ok,
    )
