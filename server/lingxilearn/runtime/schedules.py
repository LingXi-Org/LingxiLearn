"""Agent-proposed schedule validation and the independent lease worker."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .sim_semantics import SimRuntimeError

try:  # Optional at import time so SQLite/unit-test installs stay lightweight.
    from croniter import croniter
except ImportError:  # pragma: no cover - exercised only in minimal installs
    croniter = None


def validate_schedule(cron: str, timezone: str) -> tuple[str, str]:
    expression = " ".join(str(cron or "").split())
    if len(expression.split()) != 5:
        raise SimRuntimeError("schedule cron must contain exactly five fields")
    try:
        ZoneInfo(str(timezone or "UTC"))
    except ZoneInfoNotFoundError as exc:
        raise SimRuntimeError(f"unknown IANA timezone: {timezone}") from exc
    if croniter is not None and not croniter.is_valid(expression):
        raise SimRuntimeError("invalid cron expression")
    if croniter is None and any(
        not field or any(char not in "*/,-0123456789" for char in field)
        for field in expression.split()
    ):
        raise SimRuntimeError("invalid cron expression")
    if croniter is None:
        _parse_cron_field(expression.split()[0], 0, 59)
        _parse_cron_field(expression.split()[1], 0, 23)
        _parse_cron_field(expression.split()[2], 1, 31)
        _parse_cron_field(expression.split()[3], 1, 12)
        _parse_cron_field(expression.split()[4], 0, 7)
    return expression, str(timezone or "UTC")


def next_schedule_time(cron: str, timezone: str, after: datetime) -> datetime:
    expression, zone = validate_schedule(cron, timezone)
    if after.tzinfo is None:
        after = after.replace(tzinfo=UTC)
    local_after = after.astimezone(ZoneInfo(zone))
    if croniter is not None:
        return croniter(expression, local_after).get_next(datetime).astimezone(UTC)
    # Development images may omit croniter. This small parser covers the full
    # five-field cron grammar (lists, ranges and steps) for deterministic
    # local scheduling instead of silently treating ``*/15`` as daily.
    fields = expression.split()
    minute_values = _parse_cron_field(fields[0], 0, 59)
    hour_values = _parse_cron_field(fields[1], 0, 23)
    day_values = _parse_cron_field(fields[2], 1, 31)
    month_values = _parse_cron_field(fields[3], 1, 12)
    weekday_values = _parse_cron_field(fields[4], 0, 7)
    weekday_values = {0 if value == 7 else value for value in weekday_values}
    day_restricted = fields[2] != "*"
    weekday_restricted = fields[4] != "*"
    candidate = local_after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(366 * 24 * 60 + 1):
        cron_weekday = (candidate.weekday() + 1) % 7
        day_matches = candidate.day in day_values
        weekday_matches = cron_weekday in weekday_values
        day_ok = (
            day_matches or weekday_matches
            if day_restricted and weekday_restricted
            else day_matches and weekday_matches
        )
        if (
            candidate.minute in minute_values
            and candidate.hour in hour_values
            and candidate.month in month_values
            and day_ok
        ):
            return candidate.astimezone(UTC)
        candidate += timedelta(minutes=1)
    raise SimRuntimeError("cron expression has no occurrence within one year")


def _parse_cron_field(value: str, minimum: int, maximum: int) -> set[int]:
    result: set[int] = set()
    for token in value.split(","):
        if not token:
            raise SimRuntimeError("invalid cron expression")
        base, _, step_text = token.partition("/")
        try:
            step = int(step_text) if step_text else 1
        except ValueError as exc:
            raise SimRuntimeError("invalid cron expression") from exc
        if step < 1:
            raise SimRuntimeError("invalid cron expression")
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            try:
                start_text, end_text = base.split("-", 1)
                start, end = int(start_text), int(end_text)
            except ValueError as exc:
                raise SimRuntimeError("invalid cron expression") from exc
        else:
            try:
                start = end = int(base)
            except ValueError as exc:
                raise SimRuntimeError("invalid cron expression") from exc
        if start < minimum or end > maximum or start > end:
            raise SimRuntimeError("invalid cron expression")
        result.update(range(start, end + 1, step))
    if not result:
        raise SimRuntimeError("invalid cron expression")
    return result


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
            except Exception:  # noqa: BLE001 - worker must continue after one bad proposal
                # A failed claim is released by lease expiry; continue polling.
                pass
            await asyncio.sleep(max(0.5, interval_seconds))
