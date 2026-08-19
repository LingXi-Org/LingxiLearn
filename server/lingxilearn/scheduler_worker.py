"""Standalone scheduler process for Compose and production deployments."""

from __future__ import annotations

import asyncio
import uuid

from .application import ApplicationServices
from .config import get_settings
from .runtime.loop import GRAPH_NAME as LOOP_GRAPH_NAME
from .runtime.loop import GRAPH_VERSION as LOOP_GRAPH_VERSION
from .runtime.schedules import SchedulerWorker


async def main() -> None:
    services = ApplicationServices(get_settings())
    await services.startup()

    async def launch(claim: dict) -> str:
        task_id = f"scheduled-task-{uuid.uuid4().hex}"
        await services.agent_tasks.create_agent_task(
            task_id=task_id,
            learner_id=claim["learner_id"],
            prompt=claim["prompt"],
            resources=claim.get("resources") or [],
            schedule_id=claim["schedule_id"],
            scheduled_for=claim["scheduled_for"],
            graph_version=claim.get("graph_version") or f"{LOOP_GRAPH_NAME}@{LOOP_GRAPH_VERSION}",
        )
        for _ in range(40):
            snapshot = await services.agent_tasks.agent_task_snapshot(task_id, claim["learner_id"])
            if snapshot.get("current_execution_id"):
                return str(snapshot["current_execution_id"])
            await asyncio.sleep(0.25)
        raise RuntimeError("scheduled task did not create an execution")

    try:
        await SchedulerWorker(services.agent_task_repository, launch).serve()
    finally:
        await services.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
