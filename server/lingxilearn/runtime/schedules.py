"""Agent-proposed schedule validation and the independent lease worker."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

from .execution import ExecutionError

logger = logging.getLogger(__name__)


def validate_schedule(cron: str, timezone: str) -> tuple[str, str]:
    expression = " ".join(str(cron or "").split())
    if len(expression.split()) != 5:
        raise ExecutionError("schedule cron must contain exactly five fields")
    try:
        ZoneInfo(str(timezone or "UTC"))
    except ZoneInfoNotFoundError as exc:
        raise ExecutionError(f"unknown IANA timezone: {timezone}") from exc
    if not croniter.is_valid(expression):
        raise ExecutionError("invalid cron expression")
    return expression, str(timezone or "UTC")


def next_schedule_time(cron: str, timezone: str, after: datetime) -> datetime:
    expression, zone = validate_schedule(cron, timezone)
    if after.tzinfo is None:
        after = after.replace(tzinfo=UTC)
    local_after = after.astimezone(ZoneInfo(zone))
    return croniter(expression, local_after).get_next(datetime).astimezone(UTC)


class SchedulerWorker:
    """Lease and dispatch due schedules; safe to run in multiple processes."""

    def __init__(
        self,
        tasks: Any,
        launch: Callable[[dict[str, Any]], Awaitable[str]],
        *,
        owner: str | None = None,
    ) -> None:
        self.tasks = tasks
        self.launch = launch
        self.owner = owner or f"scheduler-{os.getpid()}-{uuid.uuid4().hex[:8]}"

    async def run_once(self, now: datetime | None = None) -> dict[str, Any] | None:
        moment = now or datetime.now(UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        claim = await self.tasks.claim_due_schedule(owner=self.owner, now=moment)
        if claim is None:
            return None
        execution_id = await self.launch(claim)
        next_run = next_schedule_time(claim["cron"], claim["timezone"], claim["scheduled_for"])
        # A restart may find a single old slot after a long outage.  Execute
        # that one catch-up instance, then advance directly past any further
        # missed occurrences so the worker never floods the learner with a
        # backlog of overlapping runs.
        while next_run <= moment:
            next_run = next_schedule_time(claim["cron"], claim["timezone"], next_run)
        await self.tasks.finish_schedule_claim(
            run_id=claim["run_id"],
            schedule_id=claim["schedule_id"],
            scheduled_for=claim["scheduled_for"],
            execution_id=execution_id,
            next_run_at=next_run,
        )
        return {**claim, "execution_id": execution_id, "next_run_at": next_run}

    async def serve(self, *, interval_seconds: float = 5.0) -> None:
        while True:
            try:
                await self.run_once()
            except Exception:  # noqa: BLE001 - isolate one poll/launch failure
                # A failed claim is released by lease expiry; continue polling.
                logger.exception("scheduler poll/launch failed; owner=%s", self.owner)
            await asyncio.sleep(max(0.5, interval_seconds))
