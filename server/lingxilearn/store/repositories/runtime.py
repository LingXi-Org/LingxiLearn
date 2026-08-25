"""Runtime aggregate persistence: executions, agent/skill runs, interactions."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from ..database import Database
from ..models.agent import (
    AgentTask,
    AgentTurn,
    CommandInbox,
    TransactionalOutbox,
)
from ..models.base import utcnow
from ..models.runtime import (
    AgentExecution,
    AgentInteraction,
    AgentInteractionAnswer,
    AgentRun,
    SkillRun,
)
from ..models.workspace import Workspace
from ..runtime_tables import project_runtime_events
from .common import command_dict as _command_dict


class RuntimeRepository:
    """Execution/runtime persistence. Each method owns a short transaction."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def project_runtime_event(
        self,
        *,
        learner_id: str,
        record_key: str,
        kind: str,
        task_id: str = "",
        session_id: str = "",
        sequence: int = 0,
        agent: str = "",
        payload: dict[str, Any] | None = None,
        runtime: dict[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> dict[str, Any]:
        """Project an externally replayed event into canonical runtime tables."""

        async with self.db.session() as s:
            workspace = await s.scalar(select(Workspace).where(Workspace.learner_id == learner_id))
            result = await project_runtime_events(
                s,
                learner_id=learner_id,
                records=[
                    {
                        "record_key": record_key,
                        "task_id": task_id,
                        "session_id": session_id,
                        "sequence": sequence,
                        "kind": kind,
                        "agent": agent,
                        "payload": payload or {},
                        "runtime": runtime or {},
                        "execution_id": execution_id,
                    }
                ],
                workspace=workspace,
            )
            await s.commit()
            return result[0]

    async def create_agent_execution(
        self,
        *,
        execution_id: str,
        task_id: str,
        learner_id: str,
        graph_version: str,
        trigger: str = "agent-task",
        schedule_id: str | None = None,
        scheduled_for: Any | None = None,
        turn_id: str | None = None,
        parent_execution_id: str | None = None,
        resumes_execution_id: str | None = None,
    ) -> None:
        async with self.db.session() as s:
            s.add(
                AgentExecution(
                    id=execution_id,
                    task_id=task_id,
                    learner_id=learner_id,
                    turn_id=turn_id,
                    parent_execution_id=parent_execution_id,
                    resumes_execution_id=resumes_execution_id,
                    graph_version=graph_version,
                    trigger=trigger,
                    schedule_id=schedule_id,
                    scheduled_for=scheduled_for,
                    status="running",
                    workflow_state={},
                    trace_spans=[],
                )
            )
            task = await s.get(AgentTask, task_id)
            if task is not None:
                task.current_execution_id = execution_id
                task.latest_execution_id = execution_id
                task.updated_at = utcnow()
            await s.commit()

    async def update_agent_execution(
        self,
        execution_id: str,
        *,
        status: str | None = None,
        workflow_state: dict[str, Any] | None = None,
        trace_spans: list[dict[str, Any]] | None = None,
        event_count: int | None = None,
        error: str | None = None,
        ended: bool = False,
    ) -> None:
        async with self.db.session() as s:
            row = await s.get(AgentExecution, execution_id)
            if row is None:
                return
            if status is not None:
                row.status = status
            if workflow_state is not None:
                row.workflow_state = workflow_state
            if trace_spans is not None:
                row.trace_spans = trace_spans
            if event_count is not None:
                row.event_count = event_count
            if error is not None:
                row.error = error
            if ended:
                row.ended_at = utcnow()
            row.updated_at = utcnow()
            await s.commit()

    async def get_agent_execution(
        self, execution_id: str, learner_id: str | None = None
    ) -> AgentExecution | None:
        async with self.db.session() as s:
            stmt = select(AgentExecution).where(AgentExecution.id == execution_id)
            if learner_id is not None:
                stmt = stmt.where(AgentExecution.learner_id == learner_id)
            return await s.scalar(stmt)

    async def list_agent_executions(
        self, task_id: str, learner_id: str, limit: int = 20
    ) -> list[AgentExecution]:
        async with self.db.session() as s:
            return list(
                (
                    await s.execute(
                        select(AgentExecution)
                        .where(
                            AgentExecution.task_id == task_id,
                            AgentExecution.learner_id == learner_id,
                        )
                        .order_by(AgentExecution.created_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )

    async def create_agent_run(
        self,
        *,
        agent_run_id: str,
        task_id: str,
        execution_id: str,
        provider_id: str,
        turn_id: str | None = None,
        work_item_id: str | None = None,
        parent_agent_run_id: str | None = None,
        agent_display_name: str = "",
        execution_kind: str = "model",
        capability: str = "",
        presentation_role: str = "supporting",
        status: str = "queued",
        started: bool = False,
        start_sequence: int | None = None,
        safe_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self.db.session() as s:
            row = AgentRun(
                id=agent_run_id,
                task_id=task_id,
                turn_id=turn_id,
                execution_id=execution_id,
                work_item_id=work_item_id,
                parent_agent_run_id=parent_agent_run_id,
                provider_id=provider_id,
                agent_display_name=agent_display_name,
                execution_kind=execution_kind,
                capability=capability,
                presentation_role=presentation_role,
                status="running" if started else status,
                started_at=utcnow() if started else None,
                start_sequence=start_sequence,
                safe_metadata=dict(safe_metadata or {}),
            )
            s.add(row)
            await s.commit()
            return _agent_run_dict(row)

    async def update_agent_run(
        self,
        agent_run_id: str,
        *,
        status: str | None = None,
        ended: bool = False,
        end_sequence: int | None = None,
    ) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.get(AgentRun, agent_run_id)
            if row is None:
                return None
            if status is not None:
                row.status = status
            if end_sequence is not None:
                row.end_sequence = end_sequence
            if ended:
                row.ended_at = utcnow()
            row.updated_at = utcnow()
            await s.commit()
            return _agent_run_dict(row)

    async def agent_run(self, agent_run_id: str) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.get(AgentRun, agent_run_id)
            return _agent_run_dict(row) if row is not None else None

    async def agent_runs_for_execution(self, execution_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(AgentRun)
                    .where(AgentRun.execution_id == execution_id)
                    .order_by(AgentRun.start_sequence, AgentRun.created_at)
                )
            ).all()
            return [_agent_run_dict(row) for row in rows]

    async def agent_runs_for_task(self, task_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(AgentRun)
                    .where(AgentRun.task_id == task_id)
                    .order_by(AgentRun.created_at)
                )
            ).all()
            return [_agent_run_dict(row) for row in rows]

    async def create_skill_run(
        self,
        *,
        skill_run_id: str,
        agent_run_id: str,
        task_id: str,
        execution_id: str,
        skill_id: str,
        turn_id: str | None = None,
        display_name: str = "",
        version: str = "",
        checksum: str = "",
    ) -> dict[str, Any]:
        async with self.db.session() as s:
            row = SkillRun(
                id=skill_run_id,
                agent_run_id=agent_run_id,
                task_id=task_id,
                turn_id=turn_id,
                execution_id=execution_id,
                skill_id=skill_id,
                display_name=display_name,
                version=version,
                checksum=checksum,
                status="running",
                started_at=utcnow(),
            )
            s.add(row)
            await s.commit()
            return _skill_run_dict(row)

    async def update_skill_run(
        self, skill_run_id: str, *, status: str, ended: bool = True
    ) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.get(SkillRun, skill_run_id)
            if row is None:
                return None
            row.status = status
            if ended:
                row.ended_at = utcnow()
            row.updated_at = utcnow()
            await s.commit()
            return _skill_run_dict(row)

    async def skill_runs_for_task(self, task_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(SkillRun).where(SkillRun.task_id == task_id).order_by(SkillRun.created_at)
                )
            ).all()
            return [_skill_run_dict(row) for row in rows]

    async def create_interaction(
        self,
        *,
        interaction_id: str,
        task_id: str,
        request_payload: dict[str, Any],
        turn_id: str | None = None,
        execution_id: str | None = None,
        agent_run_id: str | None = None,
        purpose: str = "clarification",
        presentation: str = "question",
        blocking: bool = True,
        reason_code: str = "",
    ) -> dict[str, Any]:
        async with self.db.session() as s:
            row = AgentInteraction(
                id=interaction_id,
                task_id=task_id,
                turn_id=turn_id,
                execution_id=execution_id,
                agent_run_id=agent_run_id,
                purpose=purpose,
                presentation=presentation,
                blocking=blocking,
                request_payload=dict(request_payload),
                status="pending",
                reason_code=reason_code,
            )
            s.add(row)
            await s.commit()
            return _interaction_dict(row)

    async def get_interaction(
        self, interaction_id: str, *, task_id: str | None = None
    ) -> dict[str, Any] | None:
        async with self.db.session() as s:
            stmt = select(AgentInteraction).where(AgentInteraction.id == interaction_id)
            if task_id is not None:
                stmt = stmt.where(AgentInteraction.task_id == task_id)
            row = await s.scalar(stmt)
            return _interaction_dict(row) if row is not None else None

    async def resolve_interaction(self, interaction_id: str) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.get(AgentInteraction, interaction_id)
            if row is None:
                return None
            row.status = "resolved"
            row.resolved_at = utcnow()
            await s.commit()
            return _interaction_dict(row)

    async def save_interaction_answer(
        self,
        *,
        interaction_id: str,
        answers: list[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Persist one idempotent structured answer; a retried key returns the original."""

        async with self.db.session() as s:
            existing = await s.scalar(
                select(AgentInteractionAnswer).where(
                    AgentInteractionAnswer.interaction_id == interaction_id,
                    AgentInteractionAnswer.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return {
                    "answers": list(existing.answers or []),
                    "created": False,
                }
            row = AgentInteractionAnswer(
                interaction_id=interaction_id,
                answers=list(answers),
                idempotency_key=idempotency_key,
            )
            s.add(row)
            try:
                await s.commit()
            except IntegrityError:
                await s.rollback()
                existing = await s.scalar(
                    select(AgentInteractionAnswer).where(
                        AgentInteractionAnswer.interaction_id == interaction_id,
                        AgentInteractionAnswer.idempotency_key == idempotency_key,
                    )
                )
                if existing is not None:
                    return {"answers": list(existing.answers or []), "created": False}
                raise
            return {"answers": list(answers), "created": True}

    async def claim_interaction_answer(
        self,
        *,
        interaction_id: str,
        task_id: str,
        answers: list[dict[str, Any]],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Resolve one blocking interaction and enqueue its continuation atomically.

        The answer, the pending→resolved transition and the durable
        continuation command commit together, so a crash between them is
        impossible: either the thread is still waiting for an answer, or a
        replayable command exists to resume the original checkpoint.  The
        continuation belongs to the interaction's own turn — answering never
        opens a new one (issue #18 §10.4).

        Outcomes: ``accepted`` (this call resolved it), ``duplicate`` (same
        idempotency key and payload — returns the original), ``conflict``
        (same key, different payload), ``already_resolved`` (another answer
        won), ``not_found``, ``invalid``.
        """

        async with self.db.session() as s:
            # Serialise concurrent answers for this thread; two different keys
            # must not both observe a pending interaction.
            task = await s.scalar(
                select(AgentTask).where(AgentTask.id == task_id).with_for_update()
            )
            if task is None:
                return {"outcome": "not_found"}
            interaction = await s.scalar(
                select(AgentInteraction)
                .where(
                    AgentInteraction.id == interaction_id,
                    AgentInteraction.task_id == task_id,
                )
                .with_for_update()
            )
            if interaction is None:
                return {"outcome": "not_found"}
            existing_answer = await s.scalar(
                select(AgentInteractionAnswer).where(
                    AgentInteractionAnswer.interaction_id == interaction_id,
                    AgentInteractionAnswer.idempotency_key == idempotency_key,
                )
            )
            if existing_answer is not None:
                if list(existing_answer.answers or []) != list(answers):
                    return {"outcome": "conflict"}
                command = await s.scalar(
                    select(CommandInbox).where(
                        CommandInbox.task_id == task_id,
                        CommandInbox.idempotency_key
                        == _interaction_command_key(interaction_id, idempotency_key),
                    )
                )
                return {
                    "outcome": "duplicate",
                    "answers": list(existing_answer.answers or []),
                    "command": _command_dict(command) if command is not None else None,
                    "interaction": _interaction_dict(interaction),
                }
            if interaction.status == "resolved":
                return {"outcome": "already_resolved", "interaction": _interaction_dict(interaction)}
            if interaction.status != "pending":
                return {"outcome": "invalid", "status": interaction.status}
            if not interaction.blocking:
                return {"outcome": "invalid", "status": "non_blocking"}

            sequence = (
                int(
                    await s.scalar(
                        select(func.coalesce(func.max(CommandInbox.sequence), 0)).where(
                            CommandInbox.task_id == task_id
                        )
                    )
                    or 0
                )
                + 1
            )
            # The continuation belongs to the turn that paused.  Older
            # interactions predating turn linkage fall back to the newest turn
            # so the command ledger's foreign key stays valid.
            turn_id = str(interaction.turn_id or "")
            if not turn_id:
                turn_id = str(
                    await s.scalar(
                        select(AgentTurn.id)
                        .where(AgentTurn.task_id == task_id)
                        .order_by(AgentTurn.turn_index.desc())
                        .limit(1)
                    )
                    or ""
                )
            if not turn_id:
                return {"outcome": "invalid", "status": "no_turn"}
            # The pending→resolved transition is the election: a conditional
            # UPDATE is atomic on both PostgreSQL and SQLite, so two concurrent
            # answers cannot both observe a pending interaction and both
            # resume the same checkpoint.
            elected = await s.execute(
                update(AgentInteraction)
                .where(
                    AgentInteraction.id == interaction_id,
                    AgentInteraction.status == "pending",
                )
                .values(status="resolved", resolved_at=utcnow())
            )
            if not int(getattr(elected, "rowcount", 0) or 0):
                await s.rollback()
                return {"outcome": "already_resolved"}
            answer_row = AgentInteractionAnswer(
                interaction_id=interaction_id,
                answers=list(answers),
                idempotency_key=idempotency_key,
            )
            # The public ``interaction.resolved`` fact commits with the
            # transition that produced it.  Appending it afterwards would let a
            # crash leave an interaction durably resolved while the replay log
            # still says the card is pending — the recap would disappear on
            # refresh (issue #18 §10.6).  The outbox row is the durable intent;
            # the service publishes it into the event log and marks it, and any
            # later replay repairs a missed publish.
            outbox = TransactionalOutbox(
                id=f"outbox_{uuid4().hex}",
                event_key=interaction_resolved_event_key(interaction_id),
                task_id=task_id,
                turn_id=turn_id,
                kind="interaction.resolved",
                safe_payload={
                    "interaction_id": interaction_id,
                    "execution_id": str(interaction.execution_id or ""),
                    "turn_id": turn_id,
                    "answers": list(answers),
                },
            )
            command = CommandInbox(
                id=f"cmd_{uuid4().hex}",
                task_id=task_id,
                turn_id=turn_id,
                sequence=sequence,
                kind="interaction_answer",
                delivery_mode="resume",
                idempotency_key=_interaction_command_key(interaction_id, idempotency_key),
                payload={
                    "interaction_id": interaction_id,
                    "answers": list(answers),
                },
            )
            s.add_all([answer_row, command, outbox])
            try:
                await s.commit()
            except IntegrityError:
                await s.rollback()
                return {"outcome": "already_resolved"}
            return {
                "outcome": "accepted",
                "answers": list(answers),
                "command": _command_dict(command),
            }

    async def pending_interaction_continuations(self) -> list[dict[str, Any]]:
        """Continuation commands whose resume never ran (crash recovery).

        A durable command that is still unconsumed means the answer committed
        but its checkpoint resume did not complete; startup replays it instead
        of leaving the thread waiting forever.
        """

        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(CommandInbox, AgentTask.learner_id)
                    .join(AgentTask, AgentTask.id == CommandInbox.task_id)
                    .where(
                        CommandInbox.kind == "interaction_answer",
                        CommandInbox.consumed_at.is_(None),
                        AgentTask.deleted_at.is_(None),
                    )
                    .order_by(CommandInbox.created_at)
                )
            ).all()
            return [
                {**_command_dict(command), "learner_id": learner_id}
                for command, learner_id in rows
            ]

    async def pending_interactions(self, task_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(AgentInteraction)
                    .where(
                        AgentInteraction.task_id == task_id,
                        AgentInteraction.status == "pending",
                    )
                    .order_by(AgentInteraction.created_at)
                )
            ).all()
            return [_interaction_dict(row) for row in rows]


def interaction_resolved_event_key(interaction_id: str) -> str:
    """Outbox key for one interaction's public ``resolved`` fact.

    Unique per interaction, so a retried answer can only ever repair the same
    row — never publish a second resolved event.
    """

    return f"interaction:{interaction_id}:resolved"



def _interaction_command_key(interaction_id: str, idempotency_key: str) -> str:
    """Command-ledger key for one interaction answer.

    Namespaced by interaction so a learner's own idempotency key cannot
    collide with a message command's key on the same task.
    """

    return f"interaction:{interaction_id}:{idempotency_key}"



def _agent_run_dict(row: AgentRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "turn_id": row.turn_id,
        "execution_id": row.execution_id,
        "work_item_id": row.work_item_id,
        "parent_agent_run_id": row.parent_agent_run_id,
        "provider_id": row.provider_id,
        "agent_display_name": row.agent_display_name,
        "execution_kind": row.execution_kind,
        "capability": row.capability,
        "presentation_role": row.presentation_role,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "start_sequence": row.start_sequence,
        "end_sequence": row.end_sequence,
        "metadata": dict(row.safe_metadata or {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }



def _skill_run_dict(row: SkillRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "agent_run_id": row.agent_run_id,
        "task_id": row.task_id,
        "turn_id": row.turn_id,
        "execution_id": row.execution_id,
        "skill_id": row.skill_id,
        "display_name": row.display_name,
        "version": row.version,
        "checksum": row.checksum,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }



def _interaction_dict(row: AgentInteraction) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "turn_id": row.turn_id,
        "execution_id": row.execution_id,
        "agent_run_id": row.agent_run_id,
        "purpose": row.purpose,
        "presentation": row.presentation,
        "blocking": bool(row.blocking),
        "request_payload": dict(row.request_payload or {}),
        "status": row.status,
        "reason_code": row.reason_code,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }

