"""REST + SSE surface.

The SSE endpoint is the interesting one: it serves from the persisted event log
rather than from the live run, honours ``Last-Event-ID``, sends heartbeat
comments while idle, and closes only when the session actually finishes.
Pausing for the learner keeps the connection open, because the session is still
alive and will emit again the moment they answer.  A learner who reloads
mid-lesson reconnects and catches up; nothing is lost because nothing was only
ever in flight.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from lingxi_identity import Principal  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ..auth import get_principal
from ..config import REPO_ROOT
from ..learner import LearnerContext
from ..service import Service
from ..store.models import (
    AgentTask,
    KnowledgeBase,
    KnowledgeDocument,
    PersonalSkill,
    Workspace,
    WorkspaceFile,
    WorkspaceTable,
)

router = APIRouter(prefix="/api")

TERMINAL = {"done", "failed", "cancelled"}
AGENT_TERMINAL = {"handed_off", "completed", "partial", "failed", "cancelled"}


def service_of(request: Request) -> Service:
    svc: Service | None = getattr(request.app.state, "service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="service_unavailable")
    return svc


async def current_learner_context(
    request: Request, principal: Principal = Depends(get_principal)
) -> LearnerContext:
    svc = service_of(request)
    try:
        return await svc.learners.get_learner_context(principal)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="invalid_identity") from exc


def not_found() -> HTTPException:
    """Use one response for missing and not-owned persistent resources."""

    return HTTPException(status_code=404, detail="resource_not_found")


@router.post("/copilot/tool-permission")
async def copilot_tool_permission(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Use Sim's native permission card contract for agent schedule proposals."""

    decisions = body.get("decisions") if isinstance(body, dict) else None
    if not isinstance(decisions, list) or not decisions or any(
        not isinstance(item, dict) for item in decisions
    ):
        raise HTTPException(status_code=422, detail="At least one decision is required")
    results: list[dict[str, Any]] = []
    svc = service_of(request)
    for item in decisions[:50]:
        if not isinstance(item, dict):
            continue
        tool_call_id = str(item.get("toolCallId") or "")
        decision = str(item.get("decision") or "")
        if not tool_call_id or decision not in {"allow", "allow_chat", "always_allow", "skip"}:
            raise HTTPException(status_code=422, detail="invalid_tool_permission_decision")
        applied_result = await svc.repo.decide_schedule_permission(
            proposal_id=tool_call_id,
            learner_id=context.learner_id,
            decision=decision,
        )
        if (
            applied_result
            and applied_result.get("applied")
            and applied_result.get("source_task_id")
        ):
            source_task_id = str(applied_result["source_task_id"])
            await svc.repo.append_agent_events(
                source_task_id,
                [
                    {
                        "kind": "schedule.permission",
                        "agent": "coordinator",
                        "payload": {
                            "toolCallId": tool_call_id,
                            "decision": decision,
                            "status": applied_result.get("status"),
                        },
                    }
                ],
            )
            svc._notify_agent(source_task_id)
        results.append(
            {
                "toolCallId": tool_call_id,
                "decision": decision,
                "applied": bool(applied_result and applied_result.get("applied")),
                "status": applied_result.get("status") if applied_result else "unknown",
                "scope": applied_result.get("scope") if applied_result else None,
            }
        )
    return {"success": True, "results": results}


async def _validated_task_context(
    request: Request,
    context: LearnerContext,
    resource_refs: list[dict[str, Any]],
    skill_ids: list[str],
) -> list[dict[str, Any]]:
    """Validate native workspace references and persist personal-skill snapshots.

    The Sim UI sends resource references as JSON rather than opaque backend IDs.
    Resolve every reference against the current learner before a task starts so
    a guessed id can never disclose another learner's files, tables, or KBs.
    Skill snapshots are copied into the task resource list to make a later run
    reproducible even if the editable personal skill changes.
    """

    svc = service_of(request)
    normalized = [dict(ref) for ref in resource_refs if isinstance(ref, dict)]
    async with svc.db.session() as session:
        workspace = await session.scalar(select(Workspace).where(Workspace.learner_id == context.learner_id))
        workspace_id = workspace.id if workspace is not None else None
        for ref in normalized:
            kind = str(ref.get("type") or ref.get("resourceType") or ref.get("kind") or "").lower()
            resource_id = str(
                ref.get("id")
                or ref.get("resourceId")
                or ref.get("fileId")
                or ref.get("tableId")
                or ref.get("knowledgeBaseId")
                or ref.get("documentId")
                or ""
            )
            if not resource_id:
                raise HTTPException(status_code=422, detail="resource_id_required")
            if kind in {"file", "files", "workspace_file"} or ref.get("fileId"):
                row = await session.scalar(
                    select(WorkspaceFile).where(
                        WorkspaceFile.id == resource_id,
                        WorkspaceFile.workspace_id == workspace_id,
                    )
                )
            elif kind in {"table", "tables", "workspace_table"} or ref.get("tableId"):
                row = await session.scalar(
                    select(WorkspaceTable).where(
                        WorkspaceTable.id == resource_id,
                        WorkspaceTable.workspace_id == workspace_id,
                    )
                )
            elif kind in {"knowledge", "knowledge_base", "kb", "document"} or ref.get("knowledgeBaseId") or ref.get("documentId"):
                if ref.get("documentId"):
                    row = await session.scalar(
                        select(KnowledgeDocument)
                        .join(KnowledgeBase, KnowledgeBase.id == KnowledgeDocument.base_id)
                        .where(
                            KnowledgeDocument.id == resource_id,
                            KnowledgeBase.learner_id == context.learner_id,
                        )
                    )
                else:
                    row = await session.scalar(
                        select(KnowledgeBase).where(
                            KnowledgeBase.id == resource_id,
                            KnowledgeBase.learner_id == context.learner_id,
                        )
                    )
            elif kind in {"task", "agent_task", "artifact"}:
                # Task and artifact references are learner-scoped as well. Do
                # not accept an opaque id here: the caller must own the task
                # that produced the reference.
                task_id = str(ref.get("taskId") or resource_id)
                row = await session.scalar(
                    select(AgentTask).where(
                        AgentTask.id == task_id,
                        AgentTask.learner_id == context.learner_id,
                    )
                )
            elif kind == "skill":
                skill_id = str(ref.get("skillId") or resource_id)
                row = await session.scalar(
                    select(PersonalSkill).where(
                        PersonalSkill.id == skill_id,
                        PersonalSkill.learner_id == context.learner_id,
                    )
                )
            else:
                raise HTTPException(status_code=422, detail="unsupported_resource_type")
            if row is None:
                raise not_found()

        if skill_ids:
            rows = (
                await session.execute(
                    select(PersonalSkill).where(
                        PersonalSkill.learner_id == context.learner_id,
                        PersonalSkill.id.in_(skill_ids),
                    )
                )
            ).scalars().all()
            found = {row.id for row in rows}
            if found != set(skill_ids):
                raise not_found()
            normalized.extend(
                {
                    "type": "skill",
                    "skillId": row.id,
                    "name": row.name,
                    "version": row.version,
                    "snapshot": row.content,
                }
                for row in rows
            )
    return normalized


# --------------------------------------------------------------------------
# Health & catalogue
# --------------------------------------------------------------------------


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    svc = service_of(request)
    try:
        db_ok = await svc.db.ping()
    except Exception:  # noqa: BLE001 - health must answer even when the DB is down
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "brain": svc.brain.name if svc.brain else "unconfigured",
        "agent": {
            "configured": svc.settings.agents_configured,
            "model": svc.settings.agent_model,
        },
        "packs": sorted(svc.packs),
        "tools": len(svc.registry.specs),
    }


@router.get("/packs")
async def list_packs(request: Request) -> dict[str, Any]:
    svc = service_of(request)
    return {
        "packs": [
            {
                "id": pack.id,
                "title": pack.title,
                "version": pack.version,
                "description": pack.description,
                "concepts": [
                    {"id": c.id, "title": c.title, "summary": c.summary, "requires": c.requires}
                    for c in pack.concepts.values()
                ],
                "missions": [
                    {
                        "id": m.id,
                        "title": m.title,
                        "subtitle": m.subtitle,
                        "summary": m.summary,
                        "why_not_chat": m.why_not_chat,
                        "concepts": list(m.concepts),
                        "estimated_minutes": m.estimated_minutes,
                        "steps": len(m.steps),
                    }
                    for m in pack.missions.values()
                ],
            }
            for pack in svc.packs.values()
        ]
    }


@router.get("/skills")
async def list_skills(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Expose the project's native LingxiSkills catalogue to the workspace."""

    skills_root = REPO_ROOT / "skills"
    skills: list[dict[str, Any]] = []
    for directory in sorted((item for item in skills_root.iterdir() if item.is_dir()), key=lambda item: item.name):
        skill_file = directory / "SKILL.md"
        if not skill_file.is_file():
            continue
        raw = skill_file.read_text(encoding="utf-8")
        _, _, body = raw.partition("---\n")
        metadata: dict[str, str] = {}
        description_lines: list[str] = []
        in_description = False
        for line in body.splitlines() if body else raw.splitlines():
            if line.strip() == "---":
                break
            if line.startswith("name:"):
                metadata["name"] = line.split(":", 1)[1].strip()
                in_description = False
                continue
            if line.startswith("  display-name:"):
                metadata["display_name"] = line.split(":", 1)[1].strip()
                in_description = False
                continue
            if line.startswith("  display-description:"):
                metadata["display_description"] = line.split(":", 1)[1].strip()
                in_description = False
                continue
            if line.startswith("  version:"):
                metadata["version"] = line.split(":", 1)[1].strip()
                in_description = False
                continue
            if line.startswith("license:"):
                metadata["license"] = line.split(":", 1)[1].strip()
                in_description = False
                continue
            if line.startswith("compatibility:"):
                metadata["compatibility"] = line.split(":", 1)[1].strip()
                in_description = False
                continue
            if line.startswith("description:"):
                in_description = True
                value = line.split(":", 1)[1].strip()
                if value and value != ">-":
                    description_lines.append(value)
                continue
            if in_description and line.startswith("  "):
                description_lines.append(line.strip())
                continue
            in_description = False
        skills.append({
            "id": metadata.get("name", directory.name),
            "name": metadata.get("name", directory.name),
            "display_name": metadata.get("display_name", metadata.get("name", directory.name)),
            "description": metadata.get("display_description", " ".join(description_lines)).strip(),
            "version": metadata.get("version", ""),
            "license": metadata.get("license", ""),
            "compatibility": metadata.get("compatibility", ""),
            "content": raw,
            "source": "system",
            "is_system": True,
        })
    svc = service_of(request)
    async with svc.db.session() as session:
        personal = (
            await session.execute(
                select(PersonalSkill).where(PersonalSkill.learner_id == context.learner_id)
            )
        ).scalars().all()
    skills.extend(
        {
            "id": row.id,
            "name": row.name,
            "display_name": row.name,
            "description": row.description,
            "content": row.content,
            "version": row.version,
            "source": "personal",
            "is_system": False,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in personal
    )
    return {"skills": skills}


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------


class CreateSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mission_id: str
    pack_id: str


class AnswerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: Any


class CreateAgentTask(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt: str = Field(min_length=1, max_length=4000)
    attachments: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    skill_ids: list[str] = Field(default_factory=list, max_length=50)


class AgentTaskMetadataPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=4000)
    is_pinned: bool | None = None
    is_unread: bool | None = None
    resources: list[dict[str, Any]] | None = None


class AgentAttachmentUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(default="application/octet-stream", max_length=128)
    size: int = Field(ge=0, le=20 * 1024 * 1024)
    data: str = Field(min_length=1)


class AgentMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str = Field(min_length=1, max_length=4000)
    attachments: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    resource_refs: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    skill_ids: list[str] = Field(default_factory=list, max_length=50)


class QuizSubmissionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: str = Field(min_length=1, max_length=128)
    answers: dict[str, Any]


@router.post("/sessions", status_code=201)
async def create_session(
    body: CreateSession,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    session_id = f"s-{uuid.uuid4().hex[:16]}"
    try:
        created = await svc.create_session(
            session_id=session_id,
            learner_id=context.learner_id,
            pack_id=body.pack_id,
            mission_id=body.mission_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return created


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    if await svc.repo.get_session_for_learner(session_id, context.learner_id) is None:
        raise not_found()
    try:
        return await svc.snapshot(session_id, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/sessions/{session_id}/answer", status_code=202)
async def answer(
    session_id: str,
    body: AnswerBody,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    record = await svc.repo.get_session_for_learner(session_id, context.learner_id)
    if record is None:
        raise not_found()
    if record.status == "running":
        raise HTTPException(status_code=409, detail="run_in_progress")
    if record.status in TERMINAL:
        raise HTTPException(status_code=409, detail=f"session_{record.status}")
    await svc.answer(session_id, body.answer, learner_id=context.learner_id)
    return {"status": "accepted"}


# --------------------------------------------------------------------------
# Intent-driven Agent Tasks
# --------------------------------------------------------------------------


@router.post("/agent-tasks", status_code=202)
async def create_agent_task(
    body: CreateAgentTask,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    task_id = f"t-{uuid.uuid4().hex[:20]}"
    try:
        task_resources = await _validated_task_context(
            request, context, body.resource_refs, body.skill_ids
        )
        created = await svc.create_agent_task(
            task_id=task_id,
            learner_id=context.learner_id,
            prompt=body.prompt,
            attachments=body.attachments,
            resources=task_resources,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return created


@router.get("/agent-tasks")
async def list_agent_tasks(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    scope = request.query_params.get("scope", "active")
    if scope not in {"active", "archived"}:
        raise HTTPException(status_code=400, detail="invalid_scope")
    return {"tasks": await service_of(request).list_agent_tasks(context.learner_id, scope=scope)}


@router.get("/agent-tasks/{task_id}")
async def get_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    try:
        return await svc.agent_task_snapshot(task_id, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/agent-tasks/{task_id}/messages", status_code=202)
async def post_agent_message(
    task_id: str,
    body: AgentMessage,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    try:
        task_resources = await _validated_task_context(
            request, context, body.resource_refs, body.skill_ids
        )
        if task_resources:
            await svc.update_agent_task(task_id, context.learner_id, resources=task_resources)
        await svc.agent_message(
            task_id,
            body.message,
            attachments=body.attachments,
            learner_id=context.learner_id,
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "accepted"}


@router.get("/agent-tasks/{task_id}/knowledge-graph")
async def get_agent_knowledge_graph(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        graph = await service_of(request).agent_knowledge_graph(task_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc
    return graph


@router.patch("/agent-tasks/{task_id}")
async def patch_agent_task(
    task_id: str,
    body: AgentTaskMetadataPatch,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await service_of(request).update_agent_task(
            task_id,
            context.learner_id,
            title=body.title,
            is_pinned=body.is_pinned,
            is_unread=body.is_unread,
            resources=body.resources,
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/agent-tasks/{task_id}")
async def delete_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await service_of(request).delete_agent_task(task_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/agent-tasks/{task_id}/restore")
async def restore_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await service_of(request).restore_agent_task(task_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/agent-tasks/{task_id}/fork", status_code=202)
async def fork_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await service_of(request).fork_agent_task(task_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/agent-tasks/{task_id}/cancel")
async def cancel_agent_task(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await service_of(request).cancel_agent_task(task_id, context.learner_id)
    except KeyError as exc:
        raise not_found() from exc


@router.post("/attachments", status_code=201)
async def upload_attachment(
    body: AgentAttachmentUpload,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await service_of(request).upload_attachment(
            learner_id=context.learner_id,
            filename=body.filename,
            media_type=body.media_type,
            size=body.size,
            encoded=body.data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/attachments/{learner_id}/{attachment_id}")
async def get_attachment(
    learner_id: str,
    attachment_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> FileResponse:
    if learner_id != context.learner_id:
        raise not_found()
    try:
        path, media_type, filename = service_of(request).attachment_path(
            learner_id, attachment_id
        )
    except KeyError as exc:
        raise not_found() from exc
    return FileResponse(path, media_type=media_type, filename=filename)


@router.post("/agent-tasks/{task_id}/quiz-submissions", status_code=202)
async def submit_agent_quiz(
    task_id: str,
    body: QuizSubmissionBody,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    try:
        return await svc.submit_agent_quiz(task_id, submission_id=body.submission_id, answers=body.answers, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=409 if detail in {"already_submitted", "task_not_waiting:awaiting_user"} or detail.startswith("task_not_waiting") else 400, detail=detail) from exc


@router.get("/agent-tasks/{task_id}/artifacts/{kind}")
async def get_agent_artifact(
    task_id: str,
    kind: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> Response:
    svc = service_of(request)
    try:
        content, media_type, filename = await svc.agent_artifact(
            task_id, kind, learner_id=context.learner_id
        )
    except KeyError as exc:
        raise not_found() from exc
    headers = {"Content-Disposition": f'inline; filename="{filename}"'}
    if kind == "visual":
        headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "img-src data:; font-src data:; connect-src 'none'; frame-src 'none'; "
            "base-uri 'none'; form-action 'none'"
        )
        headers["X-Content-Type-Options"] = "nosniff"
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/agent-tasks/{task_id}/events")
async def stream_agent_events(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    svc = service_of(request)
    try:
        await svc.agent_task_snapshot(task_id, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc

    header = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    try:
        cursor = int(header) if header else 0
    except ValueError:
        cursor = 0
    heartbeat = svc.settings.sse_heartbeat_seconds

    async def generate():  # noqa: ANN202
        nonlocal cursor
        waiter = svc.agent_waiter(task_id)
        while True:
            if await request.is_disconnected():
                return
            events = await svc.repo.agent_events_after_for_learner(
                task_id, context.learner_id, cursor
            )
            for event in events:
                cursor = event["sequence"]
                payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"

            current = await svc.agent_task_snapshot(task_id, learner_id=context.learner_id)
            if current["status"] in AGENT_TERMINAL:
                tail = await svc.repo.agent_events_after_for_learner(
                    task_id, context.learner_id, cursor
                )
                for event in tail:
                    cursor = event["sequence"]
                    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                    yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"
                yield "event: stream.end\ndata: " + json.dumps(
                    {"status": current["status"]}, ensure_ascii=False
                ) + "\n\n"
                return
            if not events:
                yield ": heartbeat\n\n"
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(waiter.wait(), timeout=heartbeat)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
@router.get("/sessions/{session_id}/report")
async def get_report(
    session_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    if await svc.repo.get_session_for_learner(session_id, context.learner_id) is None:
        raise not_found()
    stored = await svc.repo.get_report_for_learner(session_id, context.learner_id)
    if stored is not None:
        return stored
    try:
        snapshot = await svc.snapshot(session_id, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc
    if not snapshot.get("report"):
        raise HTTPException(status_code=404, detail="report_not_ready")
    return snapshot["report"]


@router.get("/sessions/{session_id}/artifact/{artifact_id}")
async def download_artifact(
    session_id: str,
    artifact_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> FileResponse:
    """Hand over the raw capture so the learner can audit us in Wireshark."""
    svc = service_of(request)
    record = await svc.repo.get_session_for_learner(session_id, context.learner_id)
    if record is None:
        raise not_found()
    pack = svc.packs.get(record.pack_id)
    mission = pack.missions.get(record.mission_id) if pack else None
    artifact = mission.artifacts.get(artifact_id) if mission else None
    if artifact is None or not Path(artifact.path).exists():  # noqa: ASYNC240
        raise HTTPException(status_code=404, detail="unknown_artifact")
    return FileResponse(
        artifact.path, media_type="application/vnd.tcpdump.pcap", filename=Path(artifact.path).name
    )
@router.get("/me/context")
async def me_context(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    return context.public_dict()


@router.get("/me/mastery")
async def me_mastery(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    return {
        "mastery": await svc.learners.get_mastery(context),
        "sessions": await svc.repo.list_sessions(context.learner_id),
    }


@router.get("/me/preferences")
async def get_preferences(
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    return {"preferences": context.preferences}


@router.patch("/me/preferences")
async def patch_preferences(
    body: dict[str, Any],
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    svc = service_of(request)
    try:
        preference = await svc.learners.update_preference(context, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"preferences": dict(preference.payload or {})}


# --------------------------------------------------------------------------
# SSE
# --------------------------------------------------------------------------


@router.get("/sessions/{session_id}/events")
async def stream_events(
    session_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> StreamingResponse:
    svc = service_of(request)
    record = await svc.repo.get_session_for_learner(session_id, context.learner_id)
    if record is None:
        raise not_found()

    header = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    try:
        cursor = int(header) if header else 0
    except ValueError:
        cursor = 0

    heartbeat = svc.settings.sse_heartbeat_seconds

    async def generate():  # noqa: ANN202
        nonlocal cursor
        waiter = svc.waiter(session_id)
        while True:
            if await request.is_disconnected():
                return
            events = await svc.repo.events_after_for_learner(
                session_id, context.learner_id, cursor
            )
            for event in events:
                cursor = event["sequence"]
                payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"

            current = await svc.repo.get_session_for_learner(
                session_id, context.learner_id
            )
            status = current.status if current else "failed"
            # Only a terminal status closes the stream. `awaiting_learner` means
            # the session is alive and will emit again the moment the learner
            # answers, so the connection is held open with heartbeats instead.
            if status in TERMINAL:
                # Drain anything appended between the query and the status read.
                tail = await svc.repo.events_after_for_learner(
                    session_id, context.learner_id, cursor
                )
                for event in tail:
                    cursor = event["sequence"]
                    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                    yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"
                yield (
                    "event: stream.end\n"
                    f"data: {json.dumps({'status': status}, ensure_ascii=False)}\n\n"
                )
                return

            if not events:
                yield ": heartbeat\n\n"
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(waiter.wait(), timeout=heartbeat)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


