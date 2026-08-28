"""HTTP endpoint for agent-produced Artifacts."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from ..learner import LearnerContext
from .dependencies import current_learner_context, not_found, services_of

router = APIRouter(prefix="/api/agent-tasks", tags=["Artifact"])


@router.get("/{task_id}/artifacts/{kind}", operation_id="download_agent_task_artifact")
async def download_agent_task_artifact(
    task_id: str,
    kind: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> Response:
    try:
        content, media_type, filename = await services_of(request).artifacts.agent_artifact(
            task_id, kind, context.learner_id
        )
    except KeyError as exc:
        raise not_found() from exc
    headers = {"Content-Disposition": f'inline; filename="{filename}"'}
    if kind == "visual":
        headers.update(
            {
                "Content-Security-Policy": (
                    "default-src 'none'; style-src 'unsafe-inline'; "
                    "script-src 'unsafe-inline'; img-src data:; font-src data:; "
                    "connect-src 'none'; frame-src 'none'; base-uri 'none'; "
                    "form-action 'none'"
                ),
                "X-Content-Type-Options": "nosniff",
            }
        )
    return Response(content=content, media_type=media_type, headers=headers)
