"""Deterministic user-facing plan projection."""

from __future__ import annotations

from .base import ProviderContext, ProviderResult, register


@register(
    "plan_presenter",
    display_name="学习计划说明",
    description="解释本轮学习安排",
    execution_kind="model",
)
async def plan_presenter(context: ProviderContext) -> ProviderResult:
    """Publish a validated plan snapshot without spending model latency."""

    tasks = context.task.inputs.get("tasks") or []
    return ProviderResult(
        data={"tasks": list(tasks), "decision_id": context.task.inputs.get("decision_id")},
        persist_as="plan_presenter",
        detail="已更新聊天中的执行计划",
    )


__all__ = ["plan_presenter"]
