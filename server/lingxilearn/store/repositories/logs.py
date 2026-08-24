from __future__ import annotations

from typing import Any

from sqlalchemy import desc, func, select

from ..models.agent import AgentTask, AgentTaskEvent
from ..models.runtime import AgentExecution


class LogRepository:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def list_tasks(self, learner_id: str, limit: int | None = None) -> list[AgentTask]:
        async with self._db.session() as session:
            query = (
                select(AgentTask)
                .where(AgentTask.learner_id == learner_id, AgentTask.deleted_at.is_(None))
                .order_by(desc(AgentTask.updated_at))
            )
            if limit is not None:
                query = query.limit(min(100, max(1, limit)))
            return list((await session.execute(query)).scalars().all())

    async def executions_by_ids(
        self, learner_id: str, execution_ids: list[str]
    ) -> dict[str, AgentExecution]:
        if not execution_ids:
            return {}
        async with self._db.session() as session:
            rows = (
                await session.execute(
                    select(AgentExecution).where(
                        AgentExecution.id.in_(execution_ids),
                        AgentExecution.learner_id == learner_id,
                    )
                )
            ).scalars()
            return {row.id: row for row in rows.all()}

    async def stats(self, learner_id: str) -> tuple[int, int, list[AgentExecution]]:
        async with self._db.session() as session:
            total = (
                await session.scalar(
                    select(func.count())
                    .select_from(AgentTask)
                    .where(AgentTask.learner_id == learner_id)
                )
                or 0
            )
            failed = (
                await session.scalar(
                    select(func.count())
                    .select_from(AgentTask)
                    .where(AgentTask.learner_id == learner_id, AgentTask.status == "failed")
                )
                or 0
            )
            rows = (
                await session.execute(
                    select(AgentExecution)
                    .where(AgentExecution.learner_id == learner_id)
                    .order_by(AgentExecution.started_at)
                )
            ).scalars()
            return int(total), int(failed), list(rows.all())

    async def events(self, task_id: str, execution_id: str | None = None) -> list[AgentTaskEvent]:
        async with self._db.session() as session:
            query = select(AgentTaskEvent).where(AgentTaskEvent.task_id == task_id)
            if execution_id is not None:
                query = query.where(AgentTaskEvent.execution_id == execution_id)
            rows = await session.execute(query.order_by(AgentTaskEvent.sequence))
            return list(rows.scalars().all())

    async def task(self, learner_id: str, task_id: str) -> AgentTask | None:
        async with self._db.session() as session:
            return await session.scalar(
                select(AgentTask).where(AgentTask.id == task_id, AgentTask.learner_id == learner_id)
            )
