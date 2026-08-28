"""WorkItem claim and lease ownership for the dispatch pipeline.

The scheduler is the dispatcher's only door to the work ledger during one
attempt: it claims the planned task's WorkItem, keeps the lease alive while
the attempt runs, and records the attempt's terminal status plus its fact
snapshot.

Dependency readiness and single-owner claim atomicity are enforced by the
ledger itself (the #56 repository boundary: ``SELECT … FOR UPDATE`` plus a
conditional lease update), so the same WorkItem can never run twice under
parallel dispatch.  The scheduler adds no policy on top — it never selects a
provider, never opens an AgentRun, and never formats an event; those belong
to the binding resolver, the execution runner, and the dispatch projector.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from contextlib import suppress
from typing import Any

from ...agents.providers import ProviderResult
from ..contracts import PlannedTask
from . import policy

HEARTBEAT_INTERVAL_SECONDS = 20
"""How often a running attempt extends its lease."""


class WorkScheduler:
    """Owns claim/lease/finish for one dispatcher against the work ledger."""

    def __init__(self, deps: Any) -> None:
        self._deps = deps

    @property
    def owner(self) -> str:
        """The lease owner identity of this dispatcher."""

        return f"dispatcher:{self._deps.task_id}"

    def tracks(self, work_id: str) -> bool:
        """True when this attempt is backed by a ledger row for ``work_id``."""

        return bool(work_id) and self._deps.work_ledger is not None

    async def claim(self, work_id: str) -> dict[str, Any] | None:
        """Claim ``work_id`` for this dispatcher, or None when not claimable.

        "Not claimable" covers both an active competing lease and a dependency
        that has not succeeded; the ledger re-checks both inside its claim
        transaction.
        """

        return await self._deps.work_ledger.claim_work_item(work_id=work_id, owner=self.owner)

    def start_heartbeat(self, work_id: str) -> asyncio.Task[None]:
        """Keep the claimed lease alive until :meth:`stop_heartbeat` runs."""

        async def keep_lease() -> None:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                if not await self._deps.work_ledger.heartbeat_work(
                    work_id=work_id, owner=self.owner
                ):
                    return

        return asyncio.create_task(keep_lease())

    @staticmethod
    async def stop_heartbeat(heartbeat: asyncio.Task[None] | None) -> None:
        if heartbeat is None:
            return
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat

    async def finish(self, work_id: str, *, status: str, result: Mapping[str, Any]) -> bool:
        """Record the attempt's terminal status and result payload."""

        return await self._deps.work_ledger.finish_work(
            work_id=work_id,
            owner=self.owner,
            status=status,
            result=dict(result),
        )

    async def record_fact_snapshot(
        self,
        *,
        claimed: Mapping[str, Any],
        task: PlannedTask,
        work_id: str,
        satisfied: bool,
        result: ProviderResult,
        evidence_ids: Sequence[str],
    ) -> None:
        """Persist the per-revision fact snapshot for the finished attempt."""

        await self._deps.work_ledger.save_fact_snapshot(
            task_id=self._deps.task_id,
            turn_id=str(claimed.get("turn_id") or ""),
            plan_revision=int(claimed.get("plan_revision") or 0),
            facts={
                "work_id": work_id,
                "task_id": task.id,
                "capability": task.capability,
                "status": policy.ledger_status_for(satisfied=satisfied),
                "satisfied": bool(satisfied),
                "schema_id": str(getattr(result, "schema_id", "")),
            },
            evidence_refs=list(evidence_ids),
            artifact_refs=list(result.artifacts),
        )


__all__ = ["HEARTBEAT_INTERVAL_SECONDS", "WorkScheduler"]
