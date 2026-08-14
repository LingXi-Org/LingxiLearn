"""Standalone scheduler process for Compose and production deployments."""

from __future__ import annotations

import asyncio
import uuid

from .config import get_settings
from .runtime.schedules import SchedulerWorker
from .service import Service


async def main() -> None:
    service = Service(get_settings())
    await service.startup()

    async def launch(claim: dict) -> str:
        task_id = f"scheduled-task-{uuid.uuid4().hex}"
        await service.create_agent_task(
            task_id=task_id,
            learner_id=claim["learner_id"],
            prompt=claim["prompt"],
            resources=claim.get("resources") or [],
            schedule_id=claim["schedule_id"],
            scheduled_for=claim["scheduled_for"],
            graph_version=claim.get("graph_version") or "knowledge_deep_dive.v1",
        )
        for _ in range(40):
            snapshot = await service.agent_task_snapshot(task_id, claim["learner_id"])
            if snapshot.get("current_execution_id"):
                return str(snapshot["current_execution_id"])
            await asyncio.sleep(0.25)
        raise RuntimeError("scheduled task did not create an execution")

    try:
        await SchedulerWorker(service.repo, launch).serve()
    finally:
        await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
