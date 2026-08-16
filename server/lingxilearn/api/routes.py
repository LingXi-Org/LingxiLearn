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

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from lingxi_identity import Principal  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ..auth import get_principal
from ..config import REPO_ROOT
from ..learner import LearnerContext
from ..service import Service, agent_task_create_payload_digest
from ..state.capabilities import CAPABILITY_INFO
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
AGENT_TERMINAL = {
    "handed_off",
    "completed",
    "partial",
    "failed",
    "timed_out",
    "budget_exceeded",
    "cancelled",
}


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
    if (
        not isinstance(decisions, list)
        or not decisions
        or any(not isinstance(item, dict) for item in decisions)
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
        workspace = await session.scalar(
            select(Workspace).where(Workspace.learner_id == context.learner_id)
        )
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
            elif (
                kind in {"knowledge", "knowledge_base", "kb", "document"}
                or ref.get("knowledgeBaseId")
                or ref.get("documentId")
            ):
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
                (
                    await session.execute(
                        select(PersonalSkill).where(
                            PersonalSkill.learner_id == context.learner_id,
                            PersonalSkill.id.in_(skill_ids),
                        )
                    )
                )
                .scalars()
                .all()
            )
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
    """Expose the project's native LingxiSkills catalogue to the workspace.

    Served from ``skill_registry`` rather than re-parsed here, so the catalogue
    the UI shows and the catalogue the orchestrator plans against are the same
    table.  ``content`` is still read from disk because the registry stores the
    manifest's meaning, not its prose.
    """

    svc = service_of(request)
    skills: list[dict[str, Any]] = []
    for entry in await svc.runtime_state.list_skills(learner_id=context.learner_id):
        manifest_path = REPO_ROOT / "skills" / entry["skill_id"] / "SKILL.md"
        skills.append(
            {
                "id": entry["skill_id"],
                "name": entry["skill_id"],
                "display_name": entry["display_name"] or entry["skill_id"],
                "description": entry["description"],
                "version": entry["version"],
                "license": "MIT",
                "compatibility": "",
                "content": manifest_path.read_text(encoding="utf-8")
                if manifest_path.is_file()
                else "",
                "source": entry["source"],
                "is_system": entry["source"] == "system",
                "capabilities": entry["capabilities"],
                "ownership": entry["ownership"],
                "provider": entry["provider"],
                "cost": entry["cost"],
                "enabled": entry["enabled"],
            }
        )
    async with svc.db.session() as session:
        personal = (
            (
                await session.execute(
                    select(PersonalSkill).where(PersonalSkill.learner_id == context.learner_id)
                )
            )
            .scalars()
            .all()
        )
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


@router.get("/skill-registry")
async def skill_registry(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """The capability registry the orchestrator plans against.

    Distinct from ``/skills``, which is the human catalogue: this is the
    machine view — capability tags, IO contracts, preconditions and cost — plus
    the capability vocabulary itself so a client can render the whole space.
    """

    svc = service_of(request)
    entries = await svc.runtime_state.list_skills(learner_id=context.learner_id)
    by_capability: dict[str, list[str]] = {}
    for entry in entries:
        if not entry["enabled"]:
            continue
        for tag in entry["capabilities"]:
            by_capability.setdefault(tag, []).append(entry["skill_id"])
    return {
        "skills": entries,
        "capabilities": [
            {
                "capability": str(item.capability),
                "label": item.label,
                "learner_facing": item.learner_facing,
                "heavy_artifact": item.heavy_artifact,
                "irreversible": item.irreversible,
                "providers": by_capability.get(str(item.capability), []),
            }
            for item in CAPABILITY_INFO.values()
        ],
    }


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
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=192)


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
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=192)


class QuizSubmissionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: str = Field(min_length=1, max_length=128)
    answers: dict[str, Any]
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=192)


class AgentConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_item_id: str = Field(min_length=1, max_length=128)
    approve: bool
    payload_digest: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=192)


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
    payload_digest = agent_task_create_payload_digest(
        prompt=body.prompt,
        attachments=body.attachments,
        resource_refs=body.resource_refs,
        skill_ids=body.skill_ids,
    )
    if body.idempotency_key:
        existing = await svc.repo.get_agent_task_by_create_idempotency_key(
            context.learner_id, body.idempotency_key
        )
        if existing is not None:
            if existing.create_payload_digest != payload_digest:
                raise HTTPException(status_code=409, detail="idempotency_key_reused")
            result = {"id": existing.id, "status": existing.status}
            if existing.error:
                result["error"] = existing.error
            return result
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
            idempotency_key=body.idempotency_key,
            create_payload_digest=payload_digest,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=409 if detail == "idempotency_key_reused" else 400,
            detail=detail,
        ) from exc
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
            idempotency_key=body.idempotency_key,
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "accepted"}


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
        path, media_type, filename = service_of(request).attachment_path(learner_id, attachment_id)
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
        return await svc.submit_agent_quiz(
            task_id,
            submission_id=body.submission_id,
            answers=body.answers,
            learner_id=context.learner_id,
            idempotency_key=body.idempotency_key,
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=409
            if detail in {"already_submitted", "task_not_waiting:awaiting_user"}
            or detail.startswith("task_not_waiting")
            else 400,
            detail=detail,
        ) from exc


@router.post("/agent-tasks/{task_id}/confirmations", status_code=202)
async def confirm_agent_work(
    task_id: str,
    body: AgentConfirmation,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    try:
        return await service_of(request).confirm_agent_work(
            task_id,
            work_item_id=body.work_item_id,
            approve=body.approve,
            payload_digest=body.payload_digest,
            idempotency_key=body.idempotency_key,
            learner_id=context.learner_id,
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/agent-tasks/{task_id}/delivery/{artifact}/ack")
async def ack_agent_delivery(
    task_id: str,
    artifact: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return await service_of(request).ack_delivery(
            task_id, artifact, learner_id=context.learner_id, idempotency_key=idempotency_key
        )
    except KeyError as exc:
        raise not_found() from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
) -> Any:
    svc = service_of(request)
    try:
        await svc.agent_task_snapshot(task_id, learner_id=context.learner_id)
    except KeyError as exc:
        raise not_found() from exc

    # History hydration uses one atomic JSON snapshot so the client can render
    # the final graph state without replaying every old event as a new run.
    if request.query_params.get("format") == "json":
        events = await svc.repo.agent_events_after_for_learner(task_id, context.learner_id, 0)
        return Response(
            content=json.dumps({"events": events}, ensure_ascii=False, separators=(",", ":")),
            media_type="application/json",
        )

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
                yield (
                    "event: stream.end\ndata: "
                    + json.dumps({"status": current["status"]}, ensure_ascii=False)
                    + "\n\n"
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


class ProfileOverride(BaseModel):
    """A learner correcting their own record. Not an agent write."""

    model_config = ConfigDict(extra="forbid")

    override: bool = True
    mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    learning_state: str | None = Field(default=None, max_length=48)
    progress: float | None = Field(default=None, ge=0.0, le=1.0)


@router.get("/me/learning-profile")
async def learning_profile(
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """The learner's study record: one row per knowledge point.

    ``next_step`` on each row is an action the learner can take, not a
    description — POST it back to act on it.
    """

    svc = service_of(request)
    rows = await svc.runtime_state.profile_for(context.learner_id)
    return {
        "profile": rows,
        "columns": {
            "learner": [
                "knowledge_point",
                "mastery",
                "learning_state",
                "progress",
                "my_questions",
                "recent_performance",
                "last_studied_at",
                "review_due_at",
                "next_step",
            ],
            "system": [
                "confidence",
                "evidence_count",
                "misconceptions",
                "prerequisites",
                "difficulty",
                "review_priority",
                "stability",
                "source_agent",
                "revision",
                "override_flag",
            ],
        },
    }


@router.post("/me/learning-profile/{knowledge_point_id}/next-step", status_code=202)
async def take_next_step(
    knowledge_point_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Act on a row's ``next_step`` by pushing it onto the goal stack.

    The runtime still decides what to run: this states an intent, exactly like
    typing it would, and the orchestrator ranks it against everything else.
    """

    svc = service_of(request)
    row = await svc.runtime_state.profile_point(context.learner_id, knowledge_point_id)
    if row is None:
        raise not_found()
    step = dict(row.get("next_step") or {})
    if not step.get("capability"):
        raise HTTPException(status_code=409, detail="no_next_step")

    task_id = f"task-{uuid.uuid4().hex}"
    label = step.get("label") or row.get("knowledge_point") or knowledge_point_id
    return await svc.create_agent_task(
        task_id=task_id,
        learner_id=context.learner_id,
        prompt=str(label),
    )


@router.patch("/me/learning-profile/{knowledge_point_id}")
async def override_learning_profile(
    knowledge_point_id: str,
    body: ProfileOverride,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Let a learner correct their own profile row.

    Sets ``override_flag`` so the state updater stops overwriting the fields the
    learner owns, while still counting new evidence against them.
    """

    svc = service_of(request)
    fields = {
        name: value
        for name, value in (
            ("mastery", body.mastery),
            ("learning_state", body.learning_state),
            ("progress", body.progress),
        )
        if value is not None
    }
    try:
        change = await svc.runtime_state.override_profile(
            learner_id=context.learner_id,
            knowledge_point_id=knowledge_point_id,
            enabled=body.override,
            fields=fields,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if change is None:
        raise not_found()
    return change.to_dict()


@router.get("/agent-tasks/{task_id}/decisions")
async def agent_task_decisions(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Every decision this task made: candidates, choice, reason, evidence, diff."""

    svc = service_of(request)
    if await svc.repo.get_agent_task_for_learner(task_id, context.learner_id) is None:
        raise not_found()
    return {"decisions": await svc.runtime_state.decisions_for_task(task_id)}


@router.get("/agent-tasks/{task_id}/runtime-graph")
async def agent_task_runtime_graph(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """Return the durable Sim-compatible runtime graph for this task."""

    svc = service_of(request)
    task = await svc.repo.get_agent_task_for_learner(task_id, context.learner_id)
    if task is None:
        raise not_found()
    execution_id = task.latest_execution_id or task.current_execution_id
    execution = (
        await svc.repo.get_agent_execution(execution_id, context.learner_id)
        if execution_id
        else None
    )
    state = dict(execution.workflow_state or {}) if execution is not None else {}
    return {
        "id": f"runtime-graph:{task_id}",
        "type": "runtime-graph",
        "taskId": task_id,
        "latestExecutionId": execution.id if execution is not None else None,
        "status": execution.status if execution is not None else task.status,
        "updatedAt": execution.updated_at.isoformat()
        if execution and execution.updated_at
        else None,
        "workflowState": state,
    }


@router.get("/agent-tasks/{task_id}/evidence")
async def agent_task_evidence(
    task_id: str,
    request: Request,
    context: LearnerContext = Depends(current_learner_context),
) -> dict[str, Any]:
    """The evidence this task produced, for drilling into a node."""

    svc = service_of(request)
    if await svc.repo.get_agent_task_for_learner(task_id, context.learner_id) is None:
        raise not_found()
    return {"evidence": await svc.runtime_state.evidence_for_task(task_id)}


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
            events = await svc.repo.events_after_for_learner(session_id, context.learner_id, cursor)
            for event in events:
                cursor = event["sequence"]
                payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                yield f"id: {cursor}\nevent: {event['kind']}\ndata: {payload}\n\n"

            current = await svc.repo.get_session_for_learner(session_id, context.learner_id)
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
