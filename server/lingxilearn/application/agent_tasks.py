"""AgentTask use-cases: thread lifecycle, learner inputs, schedules.

Owns the Thread/Turn/Interaction command side of agent tasks (issue #18):
creating threads, accepting messages/answers/quizzes, confirming work,
cancelling, and schedule proposals.  Graph execution is submitted through
:class:`~lingxilearn.application.runtime_port.RuntimeInputPort`; event
persistence goes through
:class:`~lingxilearn.application.agent_events.AgentEventService`; artifact
state through
:class:`~lingxilearn.application.artifacts.ArtifactResourceService`.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..runtime.interactions import parse_answers
from ..runtime.loop import GRAPH_NAME as LOOP_GRAPH_NAME
from ..runtime.loop import GRAPH_VERSION as LOOP_GRAPH_VERSION
from ..runtime.schedules import next_schedule_time, validate_schedule
from ..state.session_state import RuntimeStatus
from ..store.database import Database
from ..store.learner import LearnerRepository
from ..store.models.agent import AgentTask
from ..store.models.knowledge import KnowledgeBase, KnowledgeDocument
from ..store.models.table import WorkspaceTable
from ..store.models.workspace import PersonalSkill, Workspace, WorkspaceFile
from ..store.repositories.agent_tasks import AgentTaskRepository
from ..store.repositories.runtime import RuntimeRepository
from ..store.repositories.work_ledger import WorkLedgerRepository
from ..store.runtime_state import RuntimeStateRepository
from .agent_events import AgentEventService
from .artifacts import ArtifactResourceService
from .runtime_port import RuntimeInputPort
from .shared import _json_safe


def _normalize_attachment_refs(
    value: list[dict[str, Any]] | None, learner_id: str
) -> list[dict[str, Any]]:
    """Keep only the metadata needed to let agents retrieve uploaded files."""

    refs: list[dict[str, Any]] = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        filename = str(item.get("filename") or "").strip()
        if not key or not filename or not key.startswith(f"{learner_id}/"):
            continue
        try:
            size = max(0, int(item.get("size") or 0))
        except (TypeError, ValueError):
            size = 0
        refs.append(
            {
                "key": key[:512],
                "path": f"/api/attachments/{key[:512]}",
                "filename": filename[:255],
                "media_type": str(item.get("media_type") or "application/octet-stream")[:128],
                "size": size,
            }
        )
    return refs[:10]


def agent_task_create_payload_digest(
    *,
    prompt: str,
    attachments: list[dict[str, Any]] | None = None,
    resource_refs: list[dict[str, Any]] | None = None,
    skill_ids: list[str] | None = None,
    resources: list[dict[str, Any]] | None = None,
) -> str:
    """Build a stable digest for the request that creates an agent task.

    The REST route hashes the learner-facing resource references and skill ids
    before resolving them. Direct service callers can instead provide the
    already-resolved resources. Either form is stored next to the create key so
    a retry can be compared without starting another graph.
    """

    payload = {
        "version": 1,
        "prompt": " ".join(prompt.strip().split()),
        "attachments": attachments or [],
        "resource_refs": resource_refs if resource_refs is not None else resources or [],
        "skill_ids": skill_ids or [],
    }
    encoded = json.dumps(
        _json_safe(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _agent_task_create_result(record: Any) -> dict[str, Any]:
    result = {"id": record.id, "status": record.status}
    if record.error:
        result["error"] = record.error
    return result


def _prompt_with_attachments(prompt: str, attachments: list[dict[str, Any]]) -> str:
    if not attachments:
        return prompt
    lines = ["\n\n[已上传附件]"]
    lines.extend(
        f"- {item['filename']} ({item['media_type']}, {item['path'] or item['key']})"
        for item in attachments
    )
    return prompt + "\n".join(lines)


def _agents_from_trace(decisions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Which agents ran this task, derived rather than enumerated.

    The old snapshot hard-coded one key per specialist, which meant every new
    capability needed an edit here and every removed one left a dead key. This
    reads what actually happened.
    """

    seen: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        for task in (decision.get("outcome") or {}).get("tasks") or []:
            name = str(task.get("provider") or task.get("capability") or "")
            if not name:
                continue
            entry = seen.setdefault(
                name,
                {
                    "agent": name,
                    "capability": task.get("capability"),
                    "skill_id": task.get("skill_id"),
                    "runs": 0,
                    "status": "pending",
                    "detail": "",
                },
            )
            entry["runs"] += 1
            entry["status"] = str(task.get("status") or "completed")
            entry["detail"] = str(task.get("detail") or "")
    return {name: value for name, value in sorted(seen.items())}


async def _submission_snapshot(repo: AgentTaskRepository, task_id: str) -> dict[str, Any] | None:
    row = await repo.get_quiz_submission(task_id)
    if row is None:
        return None
    return {
        "submission_id": row.submission_id,
        "submitted_at": row.created_at.isoformat() if row.created_at else None,
        "total_score": row.total_score,
        "total_points": row.total_points,
        "per_question": row.per_question or [],
        "handoff_reason": row.handoff_reason,
    }


def _grade_agent_quiz(quiz: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    per_question: list[dict[str, Any]] = []
    total_score = 0.0
    total_points = 0
    for question in quiz.get("questions", []):
        qid = str(question.get("id", ""))
        points = int(question.get("points", 1))
        total_points += points
        actual = answers.get(qid)
        expected = question.get("answer")
        qtype = question.get("type")
        expected_options = (
            expected.get("option_ids", []) if isinstance(expected, dict) else expected
        )
        if qtype == "multi_choice":
            correct = set(actual or []) == set(expected_options or [])
        elif qtype == "short_text":
            text = str(actual or "").strip().casefold()
            rubric_keywords = expected.get("keywords", []) if isinstance(expected, dict) else []
            keywords = [
                str(item).strip().casefold()
                for item in (rubric_keywords or question.get("keywords", []))
                if str(item).strip()
                and not str(item).startswith(("concept:", "bloom:", "difficulty:", "purpose:"))
            ]
            correct = bool(keywords) and all(keyword in text for keyword in keywords)
        else:
            correct = str(actual or "") in {str(item) for item in (expected_options or [])}
        score = points if correct else 0
        total_score += score
        per_question.append({"id": qid, "correct": correct, "score": score, "points": points})
    return {"per_question": per_question, "total_score": total_score, "total_points": total_points}


class AgentTaskService:
    """Commands and reads for the long-lived agent-task thread."""

    def __init__(
        self,
        *,
        agent_task_repository: AgentTaskRepository,
        work_ledger: WorkLedgerRepository,
        runtime_repository: RuntimeRepository,
        runtime_state: RuntimeStateRepository,
        learner_repository: LearnerRepository,
        db: Database,
        artifact_service: ArtifactResourceService,
        event_service: AgentEventService,
        runtime: RuntimeInputPort,
        board_locks: Any,
    ) -> None:
        self._agent_tasks = agent_task_repository
        self._work_ledger = work_ledger
        self._runtime_repo = runtime_repository
        self._runtime_state = runtime_state
        self._learners = learner_repository
        self._db = db
        self._artifacts = artifact_service
        self._events = event_service
        self._runtime = runtime
        self._hold_sweep_locks = board_locks

    async def create_agent_task(
        self,
        *,
        task_id: str,
        learner_id: str,
        prompt: str,
        attachments: list[dict[str, Any]] | None = None,
        resources: list[dict[str, Any]] | None = None,
        schedule_id: str | None = None,
        scheduled_for: datetime | None = None,
        graph_version: str = f"{LOOP_GRAPH_NAME}@{LOOP_GRAPH_VERSION}",
        idempotency_key: str | None = None,
        create_payload_digest: str | None = None,
    ) -> dict[str, Any]:
        normalized = " ".join(prompt.strip().split())
        if not normalized:
            raise ValueError("prompt must not be empty")
        if len(normalized) > 4000:
            raise ValueError("prompt is too long")
        if idempotency_key is not None and not 1 <= len(idempotency_key) <= 192:
            raise ValueError("idempotency_key must be between 1 and 192 characters")
        attachment_refs = _normalize_attachment_refs(attachments, learner_id)
        payload_digest = create_payload_digest or agent_task_create_payload_digest(
            prompt=normalized,
            attachments=attachment_refs,
            resources=resources or [],
        )
        await self._learners.ensure_learner(learner_id)
        if idempotency_key:
            existing = await self._agent_tasks.get_agent_task_by_create_idempotency_key(
                learner_id, idempotency_key
            )
            if existing is not None:
                if existing.create_payload_digest != payload_digest:
                    raise ValueError("idempotency_key_reused")
                return _agent_task_create_result(existing)

        try:
            await self._agent_tasks.create_agent_task(
                id=task_id,
                learner_id=learner_id,
                create_idempotency_key=idempotency_key,
                create_payload_digest=payload_digest if idempotency_key else None,
                prompt=normalized,
                graph_version=graph_version,
                status="queued",
                resources=resources or [],
                intent={},
                lecture_result={},
                deck_result={},
                quiz_result={},
                adaptive_result={},
                handoff_result={},
                user_messages=[],
                visual_result={},
            )
        except IntegrityError:
            # Two API replicas can pass the lookup above concurrently. The
            # unique learner/key index elects one creator; the loser returns
            # the committed task instead of spawning a second graph.
            if not idempotency_key:
                raise
            existing = await self._agent_tasks.get_agent_task_by_create_idempotency_key(
                learner_id, idempotency_key
            )
            if existing is None:
                raise
            if existing.create_payload_digest != payload_digest:
                raise ValueError("idempotency_key_reused") from None
            return _agent_task_create_result(existing)
        await self._work_ledger.append_command(
            task_id=task_id,
            kind="initial_prompt",
            payload={"message": normalized, "attachments": attachment_refs},
            idempotency_key=f"task:{task_id}:initial",
        )
        await self._events.append(
            task_id,
            [{"kind": "task.started", "agent": "coordinator", "payload": {"status": "queued"}}],
        )
        if not self._runtime.model_configured:
            message = "DS_API_KEY is not configured"
            await self._agent_tasks.set_agent_task_status(task_id, "failed", message)
            await self._events.append(
                task_id,
                [{"kind": "task.failed", "agent": "coordinator", "payload": {"message": message}}],
            )
            return {"id": task_id, "status": "failed", "error": message}
        self._runtime.start_turn(
            task_id,
            learner_id,
            _prompt_with_attachments(normalized, attachment_refs),
            schedule_id=schedule_id,
            scheduled_for=scheduled_for,
        )
        return {"id": task_id, "status": "queued"}

    async def list_agent_tasks(
        self, learner_id: str, *, scope: str = "active"
    ) -> list[dict[str, Any]]:
        return await self._agent_tasks.list_agent_tasks(learner_id, scope=scope)

    async def get_agent_task_by_create_idempotency_key(
        self, learner_id: str, idempotency_key: str
    ) -> Any:
        return await self._agent_tasks.get_agent_task_by_create_idempotency_key(
            learner_id, idempotency_key
        )

    async def get_task_record(self, task_id: str, learner_id: str) -> Any:
        return await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)

    async def agent_task_snapshot(
        self, task_id: str, learner_id: str | None = None
    ) -> dict[str, Any]:
        record = (
            await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
            if learner_id is not None
            else await self._agent_tasks.get_agent_task(task_id)
        )
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        executions = await self._runtime_repo.list_agent_executions(record.id, record.learner_id)
        session_state = await self._runtime_state.get_session_state(record.id) or {}
        latest_turn = await self._work_ledger.latest_turn(record.id)
        stack = await self._runtime_state.goal_stack(record.id)
        current_goal = stack.current()
        decisions = await self._runtime_state.decisions_for_task(record.id)
        artifacts = await self._artifacts.artifact_snapshot(record)
        durable_work = await self._work_ledger.list_work(record.id)
        runtime_status = str(session_state.get("runtime_status") or "")
        current_plan = dict(session_state.get("plan") or {})
        goal_status = str(current_goal.status) if current_goal else "open"
        turn_status = str((latest_turn or {}).get("status") or "")
        work_items = [
            {
                "id": str(item.get("id") or ""),
                "candidateId": str(item.get("candidate_id") or ""),
                "capability": str(item.get("capability") or ""),
                "dependsOn": list(item.get("depends_on") or []),
                "status": str(item.get("status") or "queued"),
                "planRevision": int(item.get("plan_revision") or 0),
                "provider": str(item.get("provider") or ""),
                "payloadDigest": str(item.get("confirmation_digest") or "") or None,
            }
            for item in (durable_work or current_plan.get("tasks") or [])
            if isinstance(item, dict)
        ]
        intent_topic = str(record.title or record.prompt or "").strip()
        latest_execution = executions[0] if executions else None
        return {
            "id": record.id,
            "status": record.status,
            "threadStatus": str(getattr(record, "thread_status", "") or "open"),
            "prompt": record.prompt,
            "title": record.title or "",
            "is_pinned": bool(record.is_pinned),
            "is_unread": bool(record.is_unread),
            "deleted_at": record.deleted_at.isoformat() if record.deleted_at else None,
            "resources": record.resources or [],
            "graph_version": record.graph_version,
            "current_execution_id": record.current_execution_id,
            "latest_execution_id": record.latest_execution_id,
            "runtime_graph": {
                "id": f"runtime-graph:{record.id}",
                "type": "runtime-graph",
                "taskId": record.id,
                "latestExecutionId": record.latest_execution_id,
                "status": latest_execution.status if latest_execution else record.status,
                "updatedAt": (
                    latest_execution.updated_at.isoformat()
                    if latest_execution and latest_execution.updated_at
                    else None
                ),
            },
            "executions": [
                {
                    "id": item.id,
                    "status": item.status,
                    "trigger": item.trigger,
                    "graph_version": item.graph_version,
                    "started_at": item.started_at.isoformat() if item.started_at else None,
                    "ended_at": item.ended_at.isoformat() if item.ended_at else None,
                }
                for item in executions
            ],
            "goal": current_goal.to_dict() if current_goal else {},
            "goal_stack": list(session_state.get("goal_stack") or []),
            "runtime_status": runtime_status,
            # V2 additive compatibility fields.  The legacy status remains the
            # task row status while these expose the independent run/turn/goal
            # dimensions without forcing a frontend migration.
            "turnStatus": turn_status
            or (
                "awaiting_user"
                if runtime_status == str(RuntimeStatus.WAITING_FOR_USER)
                else "delivered"
                if runtime_status == str(RuntimeStatus.COMPLETED)
                else "failed"
                if runtime_status == str(RuntimeStatus.FAILED)
                else "active"
            ),
            "goalStatus": goal_status,
            "phase": str((latest_turn or {}).get("phase") or runtime_status.lower()),
            "executionMode": str(
                (latest_turn or {}).get("execution_mode")
                or ("deterministic_fallback" if current_plan.get("degraded") else "normal")
            ),
            "currentTurnId": str(
                (latest_turn or {}).get("id") or session_state.get("current_turn_id") or record.id
            ),
            "planRevision": int(
                (latest_turn or {}).get("revision") or session_state.get("revision") or 0
            ),
            "workItems": work_items,
            "plan": current_plan,
            "budget": dict(session_state.get("budget") or {}),
            # Which agents ran is a fact about this run, read from the decision
            # trace and the registry. There is no fixed roster to enumerate.
            "intent": {
                "topic": intent_topic,
                "learning_objective": intent_topic,
                "language": "zh-CN",
            },
            "agents": _agents_from_trace(decisions),
            "decisions": decisions,
            "artifacts": artifacts,
            "delivery": {
                "order": list(
                    (session_state.get("board") or {}).get("order")
                    or ["lesson-intro", "visual", "lecture-deck", "quiz"]
                ),
                "queue": list((session_state.get("board") or {}).get("delivery") or []),
                "cursor": int((session_state.get("board") or {}).get("cursor") or 0),
            },
            "quiz_submission": await _submission_snapshot(self._agent_tasks, record.id),
            "error": record.error,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        }

    async def update_agent_task(
        self,
        task_id: str,
        learner_id: str,
        *,
        title: str | None = None,
        is_pinned: bool | None = None,
        is_unread: bool | None = None,
        resources: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if title is not None:
            title = " ".join(title.strip().split())
            if not title:
                raise ValueError("title must not be empty")
        if resources is not None and len(resources) > 100:
            raise ValueError("too many resources")
        row = await self._agent_tasks.update_agent_task_metadata(
            task_id,
            learner_id,
            title=title,
            is_pinned=is_pinned,
            is_unread=is_unread,
            resources=resources,
        )
        if row is None:
            raise KeyError(f"unknown agent task: {task_id}")
        return {
            "id": row.id,
            "title": row.title,
            "is_pinned": row.is_pinned,
            "is_unread": row.is_unread,
            "resources": row.resources or [],
        }

    async def delete_agent_task(self, task_id: str, learner_id: str) -> dict[str, Any]:
        row = await self._agent_tasks.set_agent_task_deleted(task_id, learner_id, True)
        if row is None:
            raise KeyError(f"unknown agent task: {task_id}")
        return {"id": row.id, "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None}

    async def restore_agent_task(self, task_id: str, learner_id: str) -> dict[str, Any]:
        row = await self._agent_tasks.set_agent_task_deleted(task_id, learner_id, False)
        if row is None:
            raise KeyError(f"unknown agent task: {task_id}")
        return {"id": row.id, "deleted_at": None}

    async def fork_agent_task(self, task_id: str, learner_id: str) -> dict[str, Any]:
        source = await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
        if source is None:
            raise KeyError(f"unknown agent task: {task_id}")
        new_id = f"t-{uuid.uuid4().hex[:20]}"
        result = await self.create_agent_task(
            task_id=new_id,
            learner_id=learner_id,
            prompt=source.prompt,
            resources=list(source.resources or []),
        )
        await self._agent_tasks.update_agent_task_metadata(new_id, learner_id, title=source.title)
        return result

    async def propose_schedule(
        self,
        *,
        learner_id: str,
        prompt: str,
        cron: str,
        timezone: str = "UTC",
        resources: list[dict[str, Any]] | None = None,
        source_task_id: str | None = None,
        graph_version: str = f"{LOOP_GRAPH_NAME}@{LOOP_GRAPH_VERSION}",
    ) -> dict[str, Any]:
        """Create a pending Agent proposal; only the native Sim card can approve it."""

        expression, zone = validate_schedule(cron, timezone)
        now = datetime.now(UTC)
        proposal_id = f"schedule-proposal-{uuid.uuid4().hex}"
        row = await self._agent_tasks.create_schedule_proposal(
            id=f"schedule-{uuid.uuid4().hex}",
            proposal_id=proposal_id,
            learner_id=learner_id,
            source_task_id=source_task_id,
            prompt=" ".join(prompt.split()),
            cron=expression,
            timezone=zone,
            inputs_snapshot={"prompt": prompt, "createdAt": now.isoformat()},
            resources_snapshot=list(resources or []),
            graph_version=graph_version,
            status="proposed",
            next_run_at=next_schedule_time(expression, zone, now),
        )
        if source_task_id:
            await self._events.append(
                source_task_id,
                [
                    {
                        "kind": "schedule.proposed",
                        "agent": "coordinator",
                        "payload": {
                            "proposalId": proposal_id,
                            "toolCallId": proposal_id,
                            "toolName": "schedule.propose",
                            "cron": expression,
                            "timezone": zone,
                            "permissionDecision": "pending",
                        },
                    }
                ],
            )
            self._events.notify(source_task_id)
        return {
            "proposalId": row.proposal_id,
            "scheduleId": row.id,
            "status": row.status,
            "cron": row.cron,
            "timezone": row.timezone,
            "nextRunAt": row.next_run_at.isoformat() if row.next_run_at else None,
        }

    async def propose_schedule_revocation(
        self, *, learner_id: str, schedule_id: str
    ) -> dict[str, Any]:
        schedule = await self._agent_tasks.get_schedule(schedule_id=schedule_id, learner_id=learner_id)
        if schedule is None:
            raise KeyError(schedule_id)
        proposal_id = f"schedule-revoke-proposal-{uuid.uuid4().hex}"
        row = await self._agent_tasks.create_schedule_proposal(
            id=f"schedule-{uuid.uuid4().hex}",
            proposal_id=proposal_id,
            learner_id=learner_id,
            source_task_id=schedule.source_task_id,
            prompt=f"撤销计划：{schedule.prompt}",
            cron=schedule.cron,
            timezone=schedule.timezone,
            inputs_snapshot={"revokesScheduleId": schedule.id},
            resources_snapshot=schedule.resources_snapshot or [],
            graph_version=schedule.graph_version,
            status="proposed",
            next_run_at=schedule.next_run_at,
            revision=int(schedule.revision or 1) + 1,
        )
        if schedule.source_task_id:
            await self._events.append(
                schedule.source_task_id,
                [
                    {
                        "kind": "schedule.proposed",
                        "agent": "coordinator",
                        "payload": {
                            "proposalId": proposal_id,
                            "toolCallId": proposal_id,
                            "toolName": "schedule.revoke",
                            "revokesScheduleId": schedule.id,
                            "permissionDecision": "pending",
                        },
                    }
                ],
            )
            self._events.notify(schedule.source_task_id)
        return {
            "proposalId": row.proposal_id,
            "scheduleId": row.id,
            "revokesScheduleId": schedule.id,
            "status": row.status,
        }

    async def decide_schedule_permission(
        self, *, learner_id: str, decisions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Apply Sim permission-card decisions to schedule proposals."""

        results: list[dict[str, Any]] = []
        for item in decisions[:50]:
            if not isinstance(item, dict):
                continue
            tool_call_id = str(item.get("toolCallId") or "")
            decision = str(item.get("decision") or "")
            if not tool_call_id or decision not in {"allow", "allow_chat", "always_allow", "skip"}:
                raise ValueError("invalid_tool_permission_decision")
            applied_result = await self._agent_tasks.decide_schedule_permission(
                proposal_id=tool_call_id,
                learner_id=learner_id,
                decision=decision,
            )
            if (
                applied_result
                and applied_result.get("applied")
                and applied_result.get("source_task_id")
            ):
                source_task_id = str(applied_result["source_task_id"])
                await self._events.append(
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
                self._events.notify(source_task_id)
            results.append(
                {
                    "toolCallId": tool_call_id,
                    "decision": decision,
                    "applied": bool(applied_result and applied_result.get("applied")),
                    "status": applied_result.get("status") if applied_result else "unknown",
                    "scope": applied_result.get("scope") if applied_result else None,
                }
            )
        return results

    async def validate_task_resources(
        self,
        learner_id: str,
        resource_refs: list[dict[str, Any]],
        skill_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Validate native workspace references and persist personal-skill snapshots.

        The Sim UI sends resource references as JSON rather than opaque backend
        IDs.  Resolve every reference against the current learner before a task
        starts so a guessed id can never disclose another learner's files,
        tables, or KBs.  Skill snapshots are copied into the task resource list
        to make a later run reproducible even if the editable personal skill
        changes.

        Raises ``ValueError`` for malformed requests and ``KeyError`` for
        references that do not exist for this learner.
        """

        normalized = [dict(ref) for ref in resource_refs if isinstance(ref, dict)]
        async with self._db.session() as session:
            workspace = await session.scalar(
                select(Workspace).where(Workspace.learner_id == learner_id)
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
                    raise ValueError("resource_id_required")
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
                                KnowledgeBase.learner_id == learner_id,
                            )
                        )
                    else:
                        row = await session.scalar(
                            select(KnowledgeBase).where(
                                KnowledgeBase.id == resource_id,
                                KnowledgeBase.learner_id == learner_id,
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
                            AgentTask.learner_id == learner_id,
                        )
                    )
                elif kind == "skill":
                    skill_id = str(ref.get("skillId") or resource_id)
                    row = await session.scalar(
                        select(PersonalSkill).where(
                            PersonalSkill.id == skill_id,
                            PersonalSkill.learner_id == learner_id,
                        )
                    )
                else:
                    raise ValueError("unsupported_resource_type")
                if row is None:
                    raise KeyError("resource_not_found")

            if skill_ids:
                rows = (
                    (
                        await session.execute(
                            select(PersonalSkill).where(
                                PersonalSkill.learner_id == learner_id,
                                PersonalSkill.id.in_(skill_ids),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                found = {row.id for row in rows}
                if found != set(skill_ids):
                    raise KeyError("resource_not_found")
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

    async def agent_message(
        self,
        task_id: str,
        message: str,
        *,
        attachments: list[dict[str, Any]] | None = None,
        learner_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any] | None:
        """Accept one learner message and route it by thread state.

        Under the long-lived thread model (issue #18 §4.2) a message while the
        graph waits resumes the current turn; a message while a turn is still
        running becomes an interjection in that turn; a message on an idle
        thread — even after an earlier turn completed or failed — starts a new
        turn instead of dead-ending on a legacy terminal status.
        """

        record = await (
            self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
            if learner_id
            else self._agent_tasks.get_agent_task(task_id)
        )
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        if not message.strip():
            raise ValueError("message must not be empty")
        if str(getattr(record, "thread_status", "") or "open") == "cancelled":
            raise ValueError("thread is cancelled")
        attachment_refs = _normalize_attachment_refs(attachments, record.learner_id)
        command = None
        if idempotency_key:
            command = await self._work_ledger.append_command(
                task_id=task_id,
                kind="message",
                payload={"message": message.strip(), "attachments": attachment_refs},
                idempotency_key=idempotency_key,
            )
            # A retry of an already-enqueued command must not schedule another
            # conversation worker or append another interjection.
            if not command.get("created", True):
                if command.get("payload") != {
                    "message": message.strip(),
                    "attachments": attachment_refs,
                }:
                    raise ValueError("idempotency_key_reused")
                return {"turnId": str(command.get("turn_id") or ""), "created": False}
        if record.status == "awaiting_user":
            # Continuation of the paused turn: resume the original checkpoint.
            self._runtime.resume_turn(
                task_id,
                record.learner_id,
                {
                    "message": message,
                    "kind": "chat",
                    "attachments": attachment_refs,
                },
            )
            return {
                "turnId": str((command or {}).get("turn_id") or ""),
                "created": True,
            }
        if record.status in {"queued", "running"}:
            # Mid-turn input has one owner.  The runtime adapter decides how
            # the live graph consumes it; it must not also become a queued
            # conversation item and replay as a second turn.
            item = {
                "message": message.strip(),
                "attachments": attachment_refs,
                "received_at": datetime.now(UTC).isoformat(),
            }
            await self._runtime.submit_running_input(task_id, record.learner_id, item)
            return {
                "turnId": str((command or {}).get("turn_id") or ""),
                "created": True,
            }
        # Idle thread (previous turn delivered/failed): queue a brand-new turn.
        item = {
            "message": message.strip(),
            "attachments": attachment_refs,
            "received_at": datetime.now(UTC).isoformat(),
        }
        self._runtime.enqueue_conversation_input(task_id, record.learner_id, item)
        return {
            "turnId": str((command or {}).get("turn_id") or ""),
            "created": True,
        }

    async def answer_agent_interaction(
        self,
        task_id: str,
        interaction_id: str,
        *,
        answers: list[dict[str, Any]],
        idempotency_key: str,
        learner_id: str,
    ) -> dict[str, Any]:
        """Resolve one blocking interaction and resume the paused turn.

        The answer stays within the current turn (issue #18 §10.4): the
        original checkpoint resumes via a continuation command; no new turn or
        thread is created, and prior AgentRuns/interactions stay in history.
        """

        record = await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        interaction = await self._runtime_repo.get_interaction(interaction_id, task_id=task_id)
        if interaction is None:
            raise KeyError(f"unknown interaction: {interaction_id}")
        validated = parse_answers(answers)
        payload_answers = [answer.model_dump(mode="json", by_alias=True) for answer in validated]
        # One atomic step: persist the answer, resolve the interaction and
        # enqueue the durable continuation command.  Nothing below can leave
        # the thread resolved-but-never-resumed (issue #18 §10.4).
        claim = await self._runtime_repo.claim_interaction_answer(
            interaction_id=interaction_id,
            task_id=task_id,
            answers=payload_answers,
            idempotency_key=idempotency_key or f"{interaction_id}:answer",
        )
        outcome = str(claim.get("outcome") or "")
        if outcome == "not_found":
            raise KeyError(f"unknown interaction: {interaction_id}")
        if outcome == "conflict":
            raise ValueError("idempotency_key_reused")
        if outcome == "invalid":
            status = str(claim.get("status") or "")
            if status == "non_blocking":
                raise ValueError("non-blocking suggestions are answered by a new message")
            raise ValueError(f"interaction is {status}")
        if outcome == "already_resolved":
            # A real UI retry after a failed publish arrives with a *new*
            # idempotency key, so it lands here rather than on ``duplicate``.
            # The interaction is durably resolved, so this call must still
            # repair: publish the public fact and make sure the continuation
            # actually runs.  Both steps are idempotent, and the durable run
            # claim stops a second resume (issue #18 §10.6).
            await self._events.publish_interaction_outbox(task_id)
            self._runtime.schedule_interaction_drain(task_id, learner_id)
            return {"status": "already_resolved", "interactionId": interaction_id}
        if outcome == "duplicate":
            # A retry of the accepted answer: the continuation is already
            # durable, so report the original outcome without a second resume.
            # The retry still repairs a publish the original attempt may have
            # died before completing.
            await self._events.publish_interaction_outbox(task_id)
            return {"status": "accepted", "interactionId": interaction_id}

        await self._events.publish_interaction_outbox(task_id)

        resume = {
            "kind": "interaction_answer",
            "interaction_id": interaction_id,
            "answers": payload_answers,
        }
        # The spawn is only the fast path: the command ledger already holds the
        # continuation, so a process death here is recovered at startup.
        self._runtime.resume_turn(task_id, learner_id, resume)
        return {"status": "accepted", "interactionId": interaction_id}

    async def submit_agent_quiz(
        self,
        task_id: str,
        *,
        submission_id: str,
        answers: dict[str, Any],
        learner_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        record = await (
            self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
            if learner_id
            else self._agent_tasks.get_agent_task(task_id)
        )
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        command = await self._work_ledger.append_command(
            task_id=task_id,
            kind="quiz_submission",
            payload={"submission_id": submission_id, "answers": answers},
            idempotency_key=idempotency_key or f"quiz:{submission_id}",
        )
        if not command.get("created", True):
            if command.get("payload") != {
                "submission_id": submission_id,
                "answers": answers,
            }:
                raise ValueError("idempotency_key_reused")
            return {
                "status": "duplicate",
                "submission": await _submission_snapshot(self._agent_tasks, task_id),
            }
        existing = await self._agent_tasks.get_quiz_submission(task_id)
        if existing is not None:
            if existing.submission_id == submission_id:
                return {
                    "status": "duplicate",
                    "submission": await _submission_snapshot(self._agent_tasks, task_id),
                }
            raise ValueError("already_submitted")
        if record.status != "awaiting_user":
            raise ValueError(f"task_not_waiting:{record.status}")
        result = _grade_agent_quiz(record.quiz_result or {}, answers)
        snapshot = await self._agent_tasks.create_quiz_submission(
            task_id=task_id,
            submission_id=submission_id,
            answers=answers,
            per_question=result["per_question"],
            total_score=result["total_score"],
            total_points=result["total_points"],
        )
        await self._runtime_repo.project_runtime_event(
            learner_id=record.learner_id,
            record_key=f"assessment:{task_id}:{submission_id}",
            task_id=task_id,
            kind="assessment.submitted",
            payload=snapshot,
        )
        try:
            await self.ack_delivery(task_id, "quiz", learner_id=record.learner_id)
        except (KeyError, ValueError):
            pass
        self._runtime.resume_turn(
            task_id,
            record.learner_id,
            {"message": "已提交答题", "kind": "quiz_submit", "answers": answers},
        )
        return {"status": "accepted", "submission": await _submission_snapshot(self._agent_tasks, task_id)}

    async def confirm_agent_work(
        self,
        task_id: str,
        *,
        work_item_id: str,
        approve: bool,
        payload_digest: str,
        learner_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Approve or reject one irreversible work item by exact digest."""

        record = await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        work = await self._work_ledger.get_work(task_id=task_id, work_id=work_item_id)
        if work is None:
            raise KeyError(f"unknown work item: {work_item_id}")
        if not work.get("confirmation_digest"):
            raise ValueError("work_item_does_not_require_confirmation")
        if work["confirmation_digest"] != payload_digest:
            raise ValueError("payload_digest_mismatch")
        command = await self._work_ledger.append_command(
            task_id=task_id,
            kind="confirmation",
            payload={
                "work_item_id": work_item_id,
                "approve": approve,
                "payload_digest": payload_digest,
            },
            idempotency_key=idempotency_key,
        )
        if not command.get("created", True):
            if command.get("payload") != {
                "work_item_id": work_item_id,
                "approve": approve,
                "payload_digest": payload_digest,
            }:
                raise ValueError("idempotency_key_reused")
            return {
                "workItemId": work_item_id,
                "status": "accepted",
                "payloadDigest": payload_digest,
            }
        accepted = await self._work_ledger.confirm_work(
            work_id=work_item_id, payload_digest=payload_digest, approve=approve
        )
        if approve and not accepted:
            raise ValueError("confirmation_not_applied")
        return {
            "workItemId": work_item_id,
            "status": "queued" if approve else "cancelled",
            "payloadDigest": payload_digest,
        }

    async def ack_delivery(
        self,
        task_id: str,
        artifact: str,
        *,
        learner_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        record = await (
            self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
            if learner_id
            else self._agent_tasks.get_agent_task(task_id)
        )
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        if idempotency_key:
            command = await self._work_ledger.append_command(
                task_id=task_id,
                kind="delivery_ack",
                payload={"artifact": artifact},
                idempotency_key=idempotency_key,
            )
            if not command.get("created", True):
                if command.get("payload") != {"artifact": artifact}:
                    raise ValueError("idempotency_key_reused")
                return {"artifact": artifact, "status": "duplicate"}
        async with self._hold_sweep_locks[task_id]:
            board = await self._runtime_state.get_board(task_id)
            queue = list(board.get("delivery") or [])
            match = next((item for item in queue if item.get("artifact") == artifact), None)
            if match is None:
                raise KeyError(f"unknown delivery artifact: {artifact}")
            if match.get("state") == "consumed":
                return {
                    "artifact": artifact,
                    "cursor": int(board.get("cursor") or 0),
                    "delivery": queue,
                }
            cursor = int(board.get("cursor") or 0)
            if cursor >= len(queue) or queue[cursor].get("artifact") != artifact:
                raise ValueError("delivery_not_unlocked")
            queue[cursor]["state"] = "consumed"
            cursor += 1
            if cursor < len(queue):
                queue[cursor]["state"] = "unlocked"
                await self._events.append(
                    task_id,
                    [
                        {
                            "kind": "delivery.unlocked",
                            "agent": "delivery",
                            "payload": {
                                "artifact": queue[cursor].get("artifact"),
                                "cursor": cursor,
                            },
                        }
                    ],
                )
            board["delivery"] = queue
            board["cursor"] = cursor
            await self._runtime_state.save_board(task_id, board)
            return {"artifact": artifact, "cursor": cursor, "delivery": queue}

    async def cancel_agent_task(self, task_id: str, learner_id: str) -> dict[str, Any]:
        record = await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
        if record is None:
            raise KeyError(f"unknown agent task: {task_id}")
        if record.status in {"completed", "partial", "handed_off", "failed", "cancelled"}:
            return {"id": task_id, "status": record.status}
        for work in await self._work_ledger.list_work(task_id):
            if work.get("status") not in {"succeeded", "failed", "cancelled", "blocked"}:
                await self._work_ledger.cancel_work(task_id=task_id, work_id=str(work["id"]))
        await self._agent_tasks.set_agent_task_status(task_id, "cancelled", thread_status="cancelled")
        await self._runtime.cancel_run(task_id)
        if record.current_execution_id:
            latest = await self._agent_tasks.get_agent_task_for_learner(task_id, learner_id)
            execution_id = str(
                (latest.current_execution_id if latest else None)
                or record.current_execution_id
            )
            execution = await self._runtime_repo.get_agent_execution(execution_id, learner_id)
            if execution is not None:
                state = dict(execution.workflow_state or {})
                metadata = dict(state.get("metadata") or {})
                metadata.update({"terminal": True, "status": "cancelled", "paused": False})
                state["metadata"] = metadata
                await self._runtime_repo.update_agent_execution(
                    execution.id,
                    status="cancelled",
                    workflow_state=state,
                    ended=True,
                )
        await self._events.append(
            task_id,
            [
                {
                    "kind": "task.cancelled",
                    "agent": "coordinator",
                    "execution_id": record.current_execution_id,
                    "payload": {"status": "cancelled"},
                }
            ],
        )
        self._events.notify(task_id)
        return {"id": task_id, "status": "cancelled"}
