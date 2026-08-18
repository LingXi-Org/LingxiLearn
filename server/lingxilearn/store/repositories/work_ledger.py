"""V2 coordinator work ledger: commands, turns, work items, budget, outbox."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from ..database import Database
from ..models.agent import (
    AgentTask,
    AgentTurn,
    BudgetLedger,
    CandidateSnapshot,
    CommandInbox,
    FactSnapshot,
    TransactionalOutbox,
    WorkDependency,
    WorkItem,
    WorkResult,
)
from ..models.base import utcnow
from .common import command_dict as _command_dict
from .common import utc_datetime as _utc_datetime


class WorkLedgerRepository:
    """Coordinator ledger persistence. Each method owns a short transaction."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def append_command(
        self,
        *,
        task_id: str,
        kind: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Append one command and create its immutable turn atomically.

        A retried idempotency key returns the original command; it never
        creates a second turn or advances the command sequence.
        """

        async with self.db.session() as s:
            # Turn indexes and command sequences are task-local monotonic
            # counters.  Lock the task row so separate API processes cannot
            # both observe the same high-water mark.
            task = await s.scalar(
                select(AgentTask).where(AgentTask.id == task_id).with_for_update()
            )
            if task is None:
                raise KeyError(f"unknown agent task: {task_id}")
            existing = await s.scalar(
                select(CommandInbox).where(
                    CommandInbox.task_id == task_id,
                    CommandInbox.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                result = _command_dict(existing)
                result["created"] = False
                return result
            turn_index = (
                int(
                    await s.scalar(
                        select(func.coalesce(func.max(AgentTurn.turn_index), -1)).where(
                            AgentTurn.task_id == task_id
                        )
                    )
                )
                + 1
            )
            turn = AgentTurn(
                id=f"turn_{uuid4().hex}",
                task_id=task_id,
                turn_index=turn_index,
                status="active",
                input_payload=dict(payload),
            )
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
            command = CommandInbox(
                id=f"cmd_{uuid4().hex}",
                task_id=task_id,
                turn_id=turn.id,
                sequence=sequence,
                kind=kind,
                idempotency_key=idempotency_key,
                payload=dict(payload),
            )
            s.add_all([turn, command])
            try:
                await s.commit()
            except IntegrityError:
                await s.rollback()
                existing = await s.scalar(
                    select(CommandInbox).where(
                        CommandInbox.task_id == task_id,
                        CommandInbox.idempotency_key == idempotency_key,
                    )
                )
                if existing is None:
                    # A concurrent database may have committed the task's
                    # counters between the initial read and flush.  Re-read
                    # the high-water marks once after rollback and retry the
                    # insert with fresh immutable IDs.
                    retry_turn_index = (
                        int(
                            await s.scalar(
                                select(func.coalesce(func.max(AgentTurn.turn_index), -1)).where(
                                    AgentTurn.task_id == task_id
                                )
                            )
                        )
                        + 1
                    )
                    retry_turn = AgentTurn(
                        id=f"turn_{uuid4().hex}",
                        task_id=task_id,
                        turn_index=retry_turn_index,
                        status="active",
                        input_payload=dict(payload),
                    )
                    retry_sequence = (
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
                    retry_command = CommandInbox(
                        id=f"cmd_{uuid4().hex}",
                        task_id=task_id,
                        turn_id=retry_turn.id,
                        sequence=retry_sequence,
                        kind=kind,
                        idempotency_key=idempotency_key,
                        payload=dict(payload),
                    )
                    s.add_all([retry_turn, retry_command])
                    await s.commit()
                    result = _command_dict(retry_command)
                    result["created"] = True
                    return result
                result = _command_dict(existing)
                result["created"] = False
                return result
            result = _command_dict(command)
            result["created"] = True
            return result

    async def pending_commands(self, task_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(CommandInbox)
                    .where(CommandInbox.task_id == task_id, CommandInbox.consumed_at.is_(None))
                    .order_by(CommandInbox.sequence)
                )
            ).all()
            return [_command_dict(row) for row in rows]

    async def latest_turn(self, task_id: str) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.scalar(
                select(AgentTurn)
                .where(AgentTurn.task_id == task_id)
                .order_by(AgentTurn.turn_index.desc())
            )
            if row is None:
                return None
            return {
                "id": row.id,
                "turn_index": row.turn_index,
                "status": row.status,
                "phase": row.phase,
                "goal_status": row.goal_status,
                "execution_mode": row.execution_mode,
                "revision": int(row.revision or 0),
            }

    async def update_turn(
        self,
        *,
        turn_id: str,
        status: str,
        phase: str,
        goal_status: str = "open",
        execution_mode: str | None = None,
    ) -> bool:
        async with self.db.session() as s:
            row = await s.get(AgentTurn, turn_id)
            if row is None:
                return False
            row.status = status
            row.phase = phase
            row.goal_status = goal_status
            if execution_mode is not None:
                row.execution_mode = execution_mode
            await s.commit()
            return True

    async def consume_command(self, command_id: str) -> bool:
        async with self.db.session() as s:
            result = await s.execute(
                update(CommandInbox)
                .where(CommandInbox.id == command_id, CommandInbox.consumed_at.is_(None))
                .values(consumed_at=utcnow())
            )
            await s.commit()
            return bool(getattr(result, "rowcount", 0))

    async def create_work_plan(
        self,
        *,
        task_id: str,
        turn_id: str,
        expected_revision: int,
        items: list[dict[str, Any]],
        dependencies: Sequence[tuple[str, str]] = (),
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """CAS-submit work and dependencies as one short transaction."""

        async with self.db.session() as s:
            # Serialize reservations for a task at the database level.  The
            # in-memory Budget object is only a projection; outstanding
            # reservations and settled usage across all revisions are the
            # authoritative ledger.
            task = await s.scalar(
                select(AgentTask).where(AgentTask.id == task_id).with_for_update()
            )
            if task is None:
                return None
            turn = await s.scalar(
                select(AgentTurn)
                .where(AgentTurn.id == turn_id, AgentTurn.task_id == task_id)
                .with_for_update()
            )
            if turn is None or int(turn.revision or 0) != int(expected_revision):
                return None
            revision = int(expected_revision) + 1
            reservation = {
                "tokens": sum(int(item.get("reserved_tokens") or 0) for item in items),
                "heavy": sum(int(item.get("reserved_heavy") or 0) for item in items),
                "wall_ms": sum(int(item.get("reserved_wall_ms") or 0) for item in items),
            }
            if budget is not None and any(reservation.values()):
                ledger = await s.scalar(
                    select(BudgetLedger)
                    .where(
                        BudgetLedger.task_id == task_id,
                        BudgetLedger.turn_id == turn_id,
                        BudgetLedger.plan_revision == revision,
                    )
                    .with_for_update()
                )
                if ledger is None:
                    ledger = BudgetLedger(
                        id=f"budget_{uuid4().hex}",
                        task_id=task_id,
                        turn_id=turn_id,
                        plan_revision=revision,
                    )
                    s.add(ledger)
                totals = (
                    await s.execute(
                        select(
                            func.coalesce(func.sum(BudgetLedger.reserved_tokens), 0),
                            func.coalesce(func.sum(BudgetLedger.used_tokens), 0),
                            func.coalesce(func.sum(BudgetLedger.reserved_heavy), 0),
                            func.coalesce(func.sum(BudgetLedger.used_heavy), 0),
                            func.coalesce(func.sum(BudgetLedger.reserved_wall_ms), 0),
                            func.coalesce(func.sum(BudgetLedger.used_wall_ms), 0),
                        ).where(BudgetLedger.task_id == task_id)
                    )
                ).one()
                consumed = {
                    "tokens": int(totals[0] or 0) + int(totals[1] or 0),
                    "heavy": int(totals[2] or 0) + int(totals[3] or 0),
                    "wall_ms": int(totals[4] or 0) + int(totals[5] or 0),
                }
                limits = {
                    "tokens": max(0, int(budget.get("token_budget") or 0)),
                    "heavy": max(0, int(budget.get("max_heavy_artifacts") or 0)),
                    "wall_ms": max(0, int(budget.get("wall_ms_budget") or 0)),
                }
                if any(consumed[key] + reservation[key] > limits[key] for key in reservation):
                    await s.rollback()
                    return {"budget_exceeded": True, "reservation": reservation}
                ledger.reserved_tokens = reservation["tokens"]
                ledger.reserved_heavy = reservation["heavy"]
                ledger.reserved_wall_ms = reservation["wall_ms"]
            created: list[WorkItem] = []
            snapshotted_candidates: set[str] = set()
            for raw in items:
                item = WorkItem(
                    id=str(raw.get("id") or f"work_{uuid4().hex}"),
                    task_id=task_id,
                    turn_id=turn_id,
                    work_key=str(raw.get("work_key") or raw.get("id") or uuid4().hex),
                    plan_revision=revision,
                    candidate_id=str(raw.get("candidate_id") or ""),
                    capability=str(raw.get("capability") or ""),
                    skill_id=str(raw.get("skill_id") or ""),
                    skill_version=str(raw.get("skill_version") or ""),
                    skill_checksum=str(raw.get("skill_checksum") or ""),
                    provider=str(raw.get("provider") or ""),
                    knowledge_point_id=str(raw.get("knowledge_point_id") or ""),
                    input_payload=dict(raw.get("input_payload") or {}),
                    idempotency_key=str(
                        raw.get("idempotency_key") or f"{turn_id}:{raw.get('id') or uuid4().hex}"
                    ),
                    status=str(raw.get("status") or "queued"),
                    reserved_tokens=int(raw.get("reserved_tokens") or 0),
                    reserved_heavy=int(raw.get("reserved_heavy") or 0),
                    reserved_wall_ms=int(raw.get("reserved_wall_ms") or 0),
                    confirmation_digest=str(raw.get("confirmation_digest") or "") or None,
                )
                created.append(item)
                s.add(item)
                if item.candidate_id and item.candidate_id not in snapshotted_candidates:
                    snapshotted_candidates.add(item.candidate_id)
                    s.add(
                        CandidateSnapshot(
                            id=f"candidate_snapshot_{uuid4().hex}",
                            task_id=task_id,
                            turn_id=turn_id,
                            plan_revision=revision,
                            candidate_id=item.candidate_id,
                            capability=item.capability,
                            knowledge_point_id=item.knowledge_point_id,
                            skill_id=item.skill_id,
                            skill_version=item.skill_version,
                            skill_checksum=item.skill_checksum,
                            provider=item.provider,
                            registry_snapshot={
                                "candidate_id": item.candidate_id,
                                "skill_id": item.skill_id,
                                "skill_version": item.skill_version,
                                "skill_checksum": item.skill_checksum,
                                "provider": item.provider,
                            },
                        )
                    )
            # Flush the newly-created work items before inserting dependency
            # rows. PostgreSQL enforces both dependency foreign keys at the
            # statement boundary, and these independent ORM objects do not
            # otherwise guarantee insert ordering.
            await s.flush()
            turn.revision = revision
            for work_id, dependency_id in dependencies:
                s.add(WorkDependency(work_id=work_id, depends_on_id=dependency_id))
            await s.commit()
            return {"revision": revision, "work_items": [_work_dict(item) for item in created]}

    async def reserve_budget(
        self,
        *,
        task_id: str,
        turn_id: str,
        plan_revision: int,
        tokens: int,
        heavy: int,
        wall_ms: int,
        limits: dict[str, int],
    ) -> bool:
        """Atomically reserve remaining budget for work outside plan creation."""
        async with self.db.session() as s:
            row = await s.scalar(
                select(BudgetLedger)
                .where(
                    BudgetLedger.task_id == task_id,
                    BudgetLedger.turn_id == turn_id,
                    BudgetLedger.plan_revision == plan_revision,
                )
                .with_for_update()
            )
            if row is None:
                row = BudgetLedger(
                    id=f"budget_{uuid4().hex}",
                    task_id=task_id,
                    turn_id=turn_id,
                    plan_revision=plan_revision,
                )
                s.add(row)
            if (
                int(row.reserved_tokens or 0) + tokens + int(row.used_tokens or 0)
                > limits.get("tokens", 0)
                or int(row.reserved_heavy or 0) + heavy + int(row.used_heavy or 0)
                > limits.get("heavy", 0)
                or int(row.reserved_wall_ms or 0) + wall_ms + int(row.used_wall_ms or 0)
                > limits.get("wall_ms", 0)
            ):
                await s.rollback()
                return False
            row.reserved_tokens = int(row.reserved_tokens or 0) + max(0, tokens)
            row.reserved_heavy = int(row.reserved_heavy or 0) + max(0, heavy)
            row.reserved_wall_ms = int(row.reserved_wall_ms or 0) + max(0, wall_ms)
            await s.commit()
            return True

    async def settle_budget(
        self,
        *,
        task_id: str,
        turn_id: str,
        plan_revision: int,
        reserved_tokens: int,
        reserved_heavy: int,
        reserved_wall_ms: int,
        used_tokens: int,
        used_heavy: int,
        used_wall_ms: int,
    ) -> bool:
        async with self.db.session() as s:
            row = await s.scalar(
                select(BudgetLedger)
                .where(
                    BudgetLedger.task_id == task_id,
                    BudgetLedger.turn_id == turn_id,
                    BudgetLedger.plan_revision == plan_revision,
                )
                .with_for_update()
            )
            if row is None:
                return False
            row.reserved_tokens = max(0, int(row.reserved_tokens or 0) - max(0, reserved_tokens))
            row.reserved_heavy = max(0, int(row.reserved_heavy or 0) - max(0, reserved_heavy))
            row.reserved_wall_ms = max(0, int(row.reserved_wall_ms or 0) - max(0, reserved_wall_ms))
            row.used_tokens = int(row.used_tokens or 0) + max(0, used_tokens)
            row.used_heavy = int(row.used_heavy or 0) + max(0, used_heavy)
            row.used_wall_ms = int(row.used_wall_ms or 0) + max(0, used_wall_ms)
            await s.commit()
            return True

    async def claim_work(self, *, owner: str, lease_seconds: int = 60) -> dict[str, Any] | None:
        """Claim only queued work whose dependencies all succeeded."""

        moment = utcnow()
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(WorkItem)
                    .where(
                        (WorkItem.status == "queued")
                        | ((WorkItem.status == "leased") & (WorkItem.lease_until < moment))
                    )
                    .order_by(WorkItem.created_at)
                    .limit(32)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for row in rows:
                dependency_ids = list(
                    await s.scalars(
                        select(WorkDependency.depends_on_id).where(WorkDependency.work_id == row.id)
                    )
                )
                if dependency_ids:
                    states = list(
                        await s.scalars(
                            select(WorkItem.status).where(WorkItem.id.in_(dependency_ids))
                        )
                    )
                    if any(state != "succeeded" for state in states):
                        if any(
                            state in {"failed", "incomplete", "blocked", "cancelled"}
                            for state in states
                        ):
                            row.status = "blocked"
                        continue
                result = await s.execute(
                    update(WorkItem)
                    .where(
                        WorkItem.id == row.id,
                        (
                            (WorkItem.status == "queued")
                            | (
                                (WorkItem.status == "leased")
                                & (WorkItem.lease_until < moment)
                            )
                        ),
                    )
                    .values(
                        status="leased",
                        lease_owner=owner,
                        lease_until=moment + timedelta(seconds=max(1, lease_seconds)),
                        attempts=WorkItem.attempts + 1,
                    )
                )
                if int(getattr(result, "rowcount", 0) or 0) != 1:
                    continue
                await s.commit()
                await s.refresh(row)
                return _work_dict(row)
            await s.commit()
            return None

    async def claim_work_item(
        self, *, work_id: str, owner: str, lease_seconds: int = 60
    ) -> dict[str, Any] | None:
        """Claim a specific ledger row after rechecking its dependencies."""

        moment = utcnow()
        async with self.db.session() as s:
            row = await s.scalar(select(WorkItem).where(WorkItem.id == work_id).with_for_update())
            if row is None or row.status not in {"queued", "leased"}:
                return None
            if (
                row.status == "leased"
                and row.lease_until
                and _utc_datetime(row.lease_until) >= moment
            ):
                return None
            dependency_ids = list(
                await s.scalars(
                    select(WorkDependency.depends_on_id).where(WorkDependency.work_id == row.id)
                )
            )
            if dependency_ids:
                states = list(
                    await s.scalars(select(WorkItem.status).where(WorkItem.id.in_(dependency_ids)))
                )
                if any(state != "succeeded" for state in states):
                    if any(
                        state in {"failed", "incomplete", "blocked", "cancelled"}
                        for state in states
                    ):
                        row.status = "blocked"
                        await s.commit()
                    return None
            result = await s.execute(
                update(WorkItem)
                .where(
                    WorkItem.id == row.id,
                    (
                        (WorkItem.status == "queued")
                        | ((WorkItem.status == "leased") & (WorkItem.lease_until < moment))
                    ),
                )
                .values(
                    status="leased",
                    lease_owner=owner,
                    lease_until=moment + timedelta(seconds=max(1, lease_seconds)),
                    attempts=WorkItem.attempts + 1,
                )
            )
            if int(getattr(result, "rowcount", 0) or 0) != 1:
                await s.rollback()
                return None
            await s.commit()
            async with self.db.session() as refreshed_session:
                refreshed = await refreshed_session.get(WorkItem, work_id)
                return _work_dict(refreshed) if refreshed is not None else None

    async def heartbeat_work(self, *, work_id: str, owner: str, lease_seconds: int = 60) -> bool:
        """Extend a live lease without changing work status or ownership."""
        moment = utcnow()
        async with self.db.session() as s:
            row = await s.scalar(select(WorkItem).where(WorkItem.id == work_id))
            if row is None or row.status != "leased" or row.lease_owner != owner:
                return False
            if row.lease_until is not None and _utc_datetime(row.lease_until) < moment:
                return False
            row.lease_until = moment + timedelta(seconds=max(1, lease_seconds))
            await s.commit()
            return True

    async def recover_expired_work(self, *, limit: int = 100) -> int:
        """Requeue expired leases; dependency failures are blocked eagerly."""
        moment = utcnow()
        recovered = 0
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(WorkItem)
                    .where(WorkItem.status == "leased", WorkItem.lease_until < moment)
                    .limit(limit)
                )
            ).all()
            for row in rows:
                dependencies = list(
                    await s.scalars(
                        select(WorkDependency.depends_on_id).where(WorkDependency.work_id == row.id)
                    )
                )
                states = (
                    list(
                        await s.scalars(
                            select(WorkItem.status).where(WorkItem.id.in_(dependencies))
                        )
                    )
                    if dependencies
                    else []
                )
                row.status = (
                    "blocked"
                    if any(
                        state in {"failed", "incomplete", "blocked", "cancelled"}
                        for state in states
                    )
                    else "queued"
                )
                row.lease_owner = None
                row.lease_until = None
                recovered += 1
            await s.commit()
        return recovered

    async def cancel_work(self, *, task_id: str, work_id: str) -> bool:
        async with self.db.session() as s:
            row = await s.scalar(
                select(WorkItem).where(WorkItem.id == work_id, WorkItem.task_id == task_id)
            )
            if row is None or row.status in {"succeeded", "failed", "cancelled"}:
                return False
            row.status = "cancelled"
            row.lease_owner = None
            row.lease_until = None
            ledger = await s.scalar(
                select(BudgetLedger).where(
                    BudgetLedger.task_id == row.task_id,
                    BudgetLedger.turn_id == row.turn_id,
                    BudgetLedger.plan_revision == row.plan_revision,
                )
            )
            if ledger is not None:
                ledger.reserved_tokens = max(
                    0, int(ledger.reserved_tokens or 0) - int(row.reserved_tokens or 0)
                )
                ledger.reserved_heavy = max(
                    0, int(ledger.reserved_heavy or 0) - int(row.reserved_heavy or 0)
                )
                ledger.reserved_wall_ms = max(
                    0, int(ledger.reserved_wall_ms or 0) - int(row.reserved_wall_ms or 0)
                )
            await s.commit()
            return True

    async def finish_work(
        self,
        *,
        work_id: str,
        owner: str,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> bool:
        async with self.db.session() as s:
            item = await s.scalar(select(WorkItem).where(WorkItem.id == work_id))
            if item is None or item.lease_owner != owner or item.status != "leased":
                return False
            item.status = status
            item.lease_owner = None
            item.lease_until = None
            if result is not None:
                result_id = f"result_{uuid4().hex}"
                s.add(
                    WorkResult(
                        id=result_id,
                        work_id=item.id,
                        schema_id=str(result.get("schema_id") or ""),
                        safe_summary=str(result.get("safe_summary") or ""),
                        artifact_refs=list(result.get("artifact_refs") or []),
                        evidence_refs=list(result.get("evidence_refs") or []),
                        usage=dict(result.get("usage") or {}),
                        output_payload=dict(result.get("output_payload") or {}),
                        error_code=str(result.get("error_code") or ""),
                    )
                )
                item.result_id = result_id
                usage = dict(result.get("usage") or {})
                ledger = await s.scalar(
                    select(BudgetLedger).where(
                        BudgetLedger.task_id == item.task_id,
                        BudgetLedger.turn_id == item.turn_id,
                        BudgetLedger.plan_revision == item.plan_revision,
                    )
                )
                if ledger is not None:
                    ledger.reserved_tokens = max(
                        0, int(ledger.reserved_tokens or 0) - int(item.reserved_tokens or 0)
                    )
                    ledger.reserved_heavy = max(
                        0, int(ledger.reserved_heavy or 0) - int(item.reserved_heavy or 0)
                    )
                    ledger.reserved_wall_ms = max(
                        0, int(ledger.reserved_wall_ms or 0) - int(item.reserved_wall_ms or 0)
                    )
                    ledger.used_tokens = int(ledger.used_tokens or 0) + int(
                        usage.get("tokens") or 0
                    )
                    ledger.used_heavy = int(ledger.used_heavy or 0) + int(usage.get("heavy") or 0)
                    ledger.used_wall_ms = int(ledger.used_wall_ms or 0) + int(
                        usage.get("wall_ms") or 0
                    )
            await s.commit()
            return True

    async def get_work(self, *, task_id: str, work_id: str) -> dict[str, Any] | None:
        async with self.db.session() as s:
            row = await s.scalar(
                select(WorkItem).where(WorkItem.id == work_id, WorkItem.task_id == task_id)
            )
            return _work_dict(row) if row is not None else None

    async def list_work(self, task_id: str) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = (
                await s.scalars(
                    select(WorkItem)
                    .where(WorkItem.task_id == task_id)
                    .order_by(WorkItem.created_at)
                )
            ).all()
            return [_work_dict(row) for row in rows]

    async def confirm_work(self, *, work_id: str, payload_digest: str, approve: bool) -> bool:
        async with self.db.session() as s:
            item = await s.scalar(select(WorkItem).where(WorkItem.id == work_id))
            if (
                item is None
                or item.status != "waiting_confirmation"
                or item.confirmation_digest != payload_digest
            ):
                return False
            item.status = "queued" if approve else "cancelled"
            item.confirmed_at = utcnow() if approve else None
            if not approve:
                ledger = await s.scalar(
                    select(BudgetLedger).where(
                        BudgetLedger.task_id == item.task_id,
                        BudgetLedger.turn_id == item.turn_id,
                        BudgetLedger.plan_revision == item.plan_revision,
                    )
                )
                if ledger is not None:
                    ledger.reserved_tokens = max(
                        0, int(ledger.reserved_tokens or 0) - int(item.reserved_tokens or 0)
                    )
                    ledger.reserved_heavy = max(
                        0, int(ledger.reserved_heavy or 0) - int(item.reserved_heavy or 0)
                    )
                    ledger.reserved_wall_ms = max(
                        0, int(ledger.reserved_wall_ms or 0) - int(item.reserved_wall_ms or 0)
                    )
            await s.commit()
            return approve

    async def append_outbox(
        self,
        *,
        event_key: str,
        task_id: str,
        turn_id: str,
        plan_revision: int,
        kind: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        async with self.db.session() as s:
            row = await s.scalar(
                select(TransactionalOutbox).where(TransactionalOutbox.event_key == event_key)
            )
            if row is None:
                row = TransactionalOutbox(
                    id=f"outbox_{uuid4().hex}",
                    event_key=event_key,
                    task_id=task_id,
                    turn_id=turn_id,
                    plan_revision=plan_revision,
                    kind=kind,
                    safe_payload=dict(payload),
                )
                s.add(row)
                await s.commit()
            return {
                "id": row.id,
                "event_key": row.event_key,
                "kind": row.kind,
                "payload": dict(row.safe_payload),
                "published_at": row.published_at,
            }

    async def pending_outbox(self, *, task_id: str | None = None) -> list[dict[str, Any]]:
        """Durable facts committed with their transaction but not yet published."""

        async with self.db.session() as s:
            stmt = select(TransactionalOutbox).where(TransactionalOutbox.published_at.is_(None))
            if task_id is not None:
                stmt = stmt.where(TransactionalOutbox.task_id == task_id)
            rows = (await s.scalars(stmt.order_by(TransactionalOutbox.created_at))).all()
            return [
                {
                    "id": row.id,
                    "event_key": row.event_key,
                    "task_id": row.task_id,
                    "turn_id": row.turn_id,
                    "kind": row.kind,
                    "payload": dict(row.safe_payload or {}),
                }
                for row in rows
            ]

    async def mark_outbox_published(self, outbox_id: str) -> bool:
        """Mark one outbox row published; only the first caller gets True."""

        async with self.db.session() as s:
            result = await s.execute(
                update(TransactionalOutbox)
                .where(
                    TransactionalOutbox.id == outbox_id,
                    TransactionalOutbox.published_at.is_(None),
                )
                .values(published_at=utcnow())
            )
            await s.commit()
            return bool(getattr(result, "rowcount", 0))

    async def save_fact_snapshot(
        self,
        *,
        task_id: str,
        turn_id: str,
        plan_revision: int,
        facts: dict[str, Any],
        evidence_refs: list[str] | None = None,
        artifact_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        async with self.db.session() as s:
            row = await s.scalar(
                select(FactSnapshot).where(
                    FactSnapshot.task_id == task_id,
                    FactSnapshot.turn_id == turn_id,
                    FactSnapshot.plan_revision == plan_revision,
                )
            )
            if row is None:
                row = FactSnapshot(
                    id=f"facts_{uuid4().hex}",
                    task_id=task_id,
                    turn_id=turn_id,
                    plan_revision=plan_revision,
                    facts=dict(facts),
                    evidence_refs=list(evidence_refs or []),
                    artifact_refs=list(artifact_refs or []),
                )
                s.add(row)
                try:
                    await s.commit()
                except IntegrityError:
                    # Same-revision workers can legitimately race here.  The
                    # unique key makes the snapshot first-write-wins; recover
                    # the committed winner instead of failing the work item and
                    # blocking every dependent learner-facing capability.
                    await s.rollback()
                    row = await s.scalar(
                        select(FactSnapshot).where(
                            FactSnapshot.task_id == task_id,
                            FactSnapshot.turn_id == turn_id,
                            FactSnapshot.plan_revision == plan_revision,
                        )
                    )
                    if row is None:
                        raise
            return {
                "id": row.id,
                "facts": dict(row.facts),
                "evidence_refs": list(row.evidence_refs),
                "artifact_refs": list(row.artifact_refs),
            }

    async def work_dependencies_for_task(self, task_id: str) -> list[dict[str, Any]]:
        """Work Ledger dependency edges for one task, for the execution graph."""

        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(WorkDependency.work_id, WorkDependency.depends_on_id)
                    .join(WorkItem, WorkItem.id == WorkDependency.work_id)
                    .where(WorkItem.task_id == task_id)
                )
            ).all()
            return [{"work_id": work_id, "depends_on_id": depends_on} for work_id, depends_on in rows]


def _work_dict(row: WorkItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "turn_id": row.turn_id,
        "work_key": row.work_key,
        "plan_revision": int(row.plan_revision or 0),
        "candidate_id": row.candidate_id,
        "capability": row.capability,
        "skill_id": row.skill_id,
        "skill_version": row.skill_version,
        "skill_checksum": row.skill_checksum,
        "provider": row.provider,
        "knowledge_point_id": row.knowledge_point_id,
        "input_payload": dict(row.input_payload or {}),
        "status": row.status,
        "idempotency_key": row.idempotency_key,
        "attempts": int(row.attempts or 0),
        "lease_owner": row.lease_owner,
        "lease_until": row.lease_until.isoformat() if row.lease_until else None,
        "reserved_tokens": int(row.reserved_tokens or 0),
        "reserved_heavy": int(row.reserved_heavy or 0),
        "reserved_wall_ms": int(row.reserved_wall_ms or 0),
        "confirmation_digest": row.confirmation_digest,
        "result_id": row.result_id,
    }

