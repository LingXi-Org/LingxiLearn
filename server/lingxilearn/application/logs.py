"""Workspace log queries and their public response projections."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..store.models.base import utcnow
from ..store.repositories.logs import LogRepository
from .agent_events import AgentEventService


def _utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class LogExport:
    content: str
    media_type: str
    filename: str | None = None


class LogService:
    """Own the log use cases; HTTP adapters only supply identity and transport."""

    def __init__(self, repository: LogRepository, agent_events: AgentEventService) -> None:
        self._repository = repository
        self._agent_events = agent_events

    async def list_logs(self, learner_id: str, limit: int = 50) -> dict[str, Any]:
        tasks = await self._repository.list_tasks(learner_id, limit)
        ids = [str(task.latest_execution_id) for task in tasks if task.latest_execution_id]
        executions = await self._repository.executions_by_ids(learner_id, ids)
        logs = []
        for task in tasks:
            execution = executions.get(str(task.latest_execution_id))
            duration = 0
            if execution is not None:
                duration = max(
                    0,
                    int(
                        (
                            (_utc_datetime(execution.ended_at) or utcnow())
                            - (_utc_datetime(execution.started_at) or utcnow())
                        ).total_seconds()
                        * 1000
                    ),
                )
            logs.append(
                self._summary(
                    identifier=task.id,
                    execution_id=task.latest_execution_id or task.id,
                    status=task.status,
                    duration=duration,
                    created_at=(
                        execution.started_at.isoformat()
                        if execution is not None and execution.started_at
                        else task.created_at.isoformat()
                        if task.created_at
                        else ""
                    ),
                    trigger="agent-task",
                    job_title=task.title or None,
                    normalize_status=True,
                )
            )
        return {"success": True, "data": logs, "nextCursor": None}

    async def stats(self, learner_id: str) -> dict[str, Any]:
        total, failed, executions = await self._repository.stats(learner_id)
        now_dt = datetime.now(UTC)
        rows = [(_utc_datetime(row.started_at), _utc_datetime(row.ended_at)) for row in executions]
        durations = [
            max(0, int(((ended or now_dt) - started).total_seconds() * 1000))
            for started, ended in rows
            if started
        ]
        starts = [started for started, _ in rows if started]
        ends = [ended or now_dt for started, ended in rows if started]
        now = now_dt.isoformat()
        return {
            "workflows": [],
            "aggregateSegments": [],
            "totalRuns": int(total),
            "totalErrors": int(failed),
            "avgLatency": int(sum(durations) / len(durations)) if durations else 0,
            "timeBounds": {
                "start": min(starts).isoformat() if starts else now,
                "end": max(ends).isoformat() if ends else now,
            },
            "segmentMs": max(durations) if durations else 0,
        }

    async def export(self, learner_id: str, format: str = "json") -> LogExport:
        tasks = await self._repository.list_tasks(learner_id)
        records = [
            {
                "id": task.id,
                "status": task.status,
                "prompt": task.prompt,
                "createdAt": task.created_at.isoformat() if task.created_at else None,
                "updatedAt": task.updated_at.isoformat() if task.updated_at else None,
            }
            for task in tasks
        ]
        if format.lower() == "csv":
            buffer = io.StringIO()
            writer = csv.DictWriter(
                buffer, fieldnames=["id", "status", "prompt", "createdAt", "updatedAt"]
            )
            writer.writeheader()
            writer.writerows(records)
            return LogExport(buffer.getvalue(), "text/csv", "lingxi-logs.csv")
        return LogExport(json.dumps(records, ensure_ascii=False), "application/json")

    async def by_execution(self, learner_id: str, execution_id: str) -> dict[str, Any]:
        snapshot = await self._agent_events.agent_execution_snapshot(execution_id, learner_id)
        task_id = snapshot["taskId"]
        events = await self._repository.events(task_id, execution_id)
        metadata = snapshot["executionMetadata"]
        detail = self._summary(
            identifier=execution_id,
            execution_id=execution_id,
            status=snapshot["status"],
            duration=metadata.get("totalDurationMs") or 0,
            created_at=metadata.get("startedAt") or datetime.now(UTC).isoformat(),
            trigger=metadata.get("trigger"),
            job_title=None,
        )
        detail.update(
            executionData={
                "totalDuration": metadata.get("totalDurationMs"),
                "enhanced": True,
                "traceSpans": snapshot["traceSpans"],
                "trajectory": snapshot.get("trajectory"),
                "runtimeEvents": [self._runtime_event(event) for event in events],
                "workflowInput": {"taskId": task_id},
                "trigger": metadata.get("trigger"),
            },
            files=None,
            events=[self._public_event(event) for event in events],
            error=None,
        )
        return {"success": True, "data": detail}

    async def execution_snapshot(self, learner_id: str, execution_id: str) -> dict[str, Any]:
        snapshot = await self._agent_events.agent_execution_snapshot(execution_id, learner_id)
        metadata = snapshot.get("executionMetadata") or {}
        metadata["startedAt"] = metadata.get("startedAt") or datetime.now(UTC).isoformat()
        snapshot["executionMetadata"] = metadata
        return snapshot

    async def detail(self, learner_id: str, log_id: str) -> dict[str, Any] | None:
        task = await self._repository.task(learner_id, log_id)
        if task is None:
            return None
        events = await self._repository.events(task.id)
        snapshot = None
        if task.latest_execution_id:
            try:
                snapshot = await self._agent_events.agent_execution_snapshot(
                    task.latest_execution_id, learner_id
                )
            except KeyError:
                pass
        detail = self._summary(
            identifier=task.id,
            execution_id=task.latest_execution_id or task.id,
            status=task.status,
            duration=(snapshot or {}).get("executionMetadata", {}).get("totalDurationMs") or 0,
            created_at=task.created_at.isoformat()
            if task.created_at
            else datetime.now(UTC).isoformat(),
            trigger="agent-task",
            job_title=task.title or None,
        )
        detail.update(
            executionData={
                "totalDuration": 0,
                "enhanced": True,
                "traceSpans": (snapshot or {}).get("traceSpans") or [],
                "trajectory": (snapshot or {}).get("trajectory"),
                "runtimeEvents": [self._runtime_event(event) for event in events],
                "workflowInput": {"taskId": task.id, "prompt": task.prompt},
                "trigger": "agent-task",
            },
            files=None,
            events=[self._public_event(event, include_execution=True) for event in events],
            error=task.error or None,
        )
        return {"success": True, "data": detail}

    @staticmethod
    def _summary(
        *,
        identifier: str,
        execution_id: str,
        status: str,
        duration: int,
        created_at: str,
        trigger: str | None,
        job_title: str | None,
        normalize_status: bool = False,
    ) -> dict[str, Any]:
        public_status = (
            "completed"
            if normalize_status and status in {"completed", "partial", "handed_off"}
            else status
        )
        return {
            "id": identifier,
            "executionId": execution_id,
            "workflowId": "lingxi-agent",
            "workflowName": "LingxiGraph · Sim runtime",
            "deploymentVersionId": None,
            "deploymentVersion": None,
            "deploymentVersionName": None,
            "executionOrigin": None,
            "level": "error" if status == "failed" else "info",
            "status": public_status,
            "duration": str(duration),
            "trigger": trigger,
            "createdAt": created_at,
            "workflow": {"id": "lingxi-agent", "name": "LingxiGraph · Sim runtime"},
            "jobTitle": job_title,
            "cost": {"total": 0},
            "pauseSummary": {
                "status": "awaiting_user" if status == "awaiting_user" else None,
                "total": 1 if status == "awaiting_user" else 0,
                "resumed": 0,
            },
            "hasPendingPause": status == "awaiting_user",
        }

    @staticmethod
    def _runtime_event(event: Any) -> dict[str, Any]:
        return {
            "sequence": event.sequence,
            "kind": event.kind,
            "agent": event.agent,
            "runtime": event.runtime or {},
            "createdAt": event.created_at.isoformat() if event.created_at else None,
        }

    @staticmethod
    def _public_event(event: Any, *, include_execution: bool = False) -> dict[str, Any]:
        result = {
            "id": event.sequence,
            "sequence": event.sequence,
            "type": event.kind,
            "kind": event.kind,
            "payload": event.payload,
            "runtime": event.runtime or {},
            "createdAt": event.created_at.isoformat() if event.created_at else None,
        }
        if include_execution:
            result["executionId"] = event.execution_id
        return result
