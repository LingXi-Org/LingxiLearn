from lingxilearn.runtime.contracts import Cost, DoneCondition, OrchestrationPlan, PlannedTask


def _task(task_id: str, *, depends_on: list[str] | None = None, parallel_safe: bool = False) -> PlannedTask:
    return PlannedTask(
        id=task_id,
        capability="content.lesson_intro",
        depends_on=depends_on or [],
        done_when=DoneCondition(kind="always"),
        rationale=task_id,
        estimated_cost=Cost(parallel_safe=parallel_safe),
    )


def test_plan_preserves_dependency_tiers_for_parallel_dispatch() -> None:
    plan = OrchestrationPlan(tasks=[_task("a", parallel_safe=True), _task("b", parallel_safe=True), _task("c", depends_on=["a"])])
    tiers = plan.tiers()
    assert [[task.id for task in tier] for tier in tiers] == [["a", "b"], ["c"]]
    assert [task.id for task in plan.ordered_tasks()] == ["a", "b", "c"]


def test_parallel_safety_is_explicit_and_defaults_off() -> None:
    assert _task("safe", parallel_safe=True).estimated_cost.parallel_safe is True
    assert _task("serial").estimated_cost.parallel_safe is False
