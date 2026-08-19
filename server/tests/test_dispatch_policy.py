"""Pure tests for the dispatch outcome policy (issue #60).

The policy module is the single owner of "what did this attempt mean":
blocked / failed / incomplete / completed / held, the ledger status, and the
error code.  These tests pin the mapping so neither the scheduler nor the
runner can grow a second copy of the decision.
"""

from __future__ import annotations

from lingxilearn.agents.providers import ProviderError, ProviderResult
from lingxilearn.runtime.contracts import Cost, DoneCondition, PlannedTask
from lingxilearn.runtime.dispatch import policy
from lingxilearn.runtime.dispatch.binding import NoProvider, Resolution


def _task(*, heavy: bool = False, revision: int = 0) -> PlannedTask:
    inputs = {"revision": {"number": revision}} if revision else {}
    return PlannedTask(
        id="t1",
        capability="content.visual",
        inputs=inputs,
        done_when=DoneCondition(kind="always"),
        rationale="测试任务",
        estimated_cost=Cost(heavy_artifact=heavy),
    )


def _resolution() -> Resolution:
    return Resolution(capability="content.visual", skill_id="visual-skill", provider="p_visual")


def test_error_code_mapping_is_complete() -> None:
    assert policy.error_code_for(NoProvider("none")) == policy.NO_PROVIDER
    assert policy.error_code_for(ProviderError("declined")) == policy.PROVIDER_ERROR
    assert policy.error_code_for(RuntimeError("boom")) == policy.PROVIDER_FAILED


def test_ledger_status_maps_satisfaction() -> None:
    assert policy.ledger_status_for(satisfied=True) == "succeeded"
    assert policy.ledger_status_for(satisfied=False) == "incomplete"


def test_held_requires_artifacts_and_satisfaction() -> None:
    assert policy.is_held(ProviderResult(artifacts=["visual"]), satisfied=True) is True
    assert policy.is_held(ProviderResult(artifacts=[]), satisfied=True) is False
    assert policy.is_held(ProviderResult(artifacts=["visual"]), satisfied=False) is False


def test_blocked_outcome_without_binding() -> None:
    outcome = policy.blocked_outcome(_task(), node_id="n1", detail="not claimable")
    assert outcome.status == "blocked"
    assert outcome.satisfied is False
    assert outcome.provider == ""
    assert outcome.skill_id == ""
    assert outcome.node_id == "n1"
    assert outcome.detail == "not claimable"


def test_blocked_outcome_with_binding_carries_identity() -> None:
    outcome = policy.blocked_outcome(
        _task(), node_id="n1", detail="provider is not implemented", resolution=_resolution()
    )
    assert outcome.status == "blocked"
    assert outcome.provider == "p_visual"
    assert outcome.skill_id == "visual-skill"


def test_failure_outcome_marks_terminal_failure() -> None:
    outcome = policy.failure_outcome(
        _task(heavy=True), _resolution(), detail="ValueError: boom", node_id="n1", duration_ms=42
    )
    assert outcome.status == "failed"
    assert outcome.satisfied is False
    assert outcome.detail == "ValueError: boom"
    assert outcome.duration_ms == 42
    assert outcome.heavy is True


def test_success_outcome_completed_when_satisfied() -> None:
    result = ProviderResult(
        status="completed",
        learner_message="给你",
        artifacts=["visual"],
        detail="产物完成",
        tokens_used=123,
    )
    outcome = policy.success_outcome(
        _task(revision=2),
        _resolution(),
        result,
        node_id="n1",
        satisfied=True,
        detail="",
        evidence_ids=["ev1"],
        duration_ms=55,
        held=True,
    )
    assert outcome.status == "completed"
    assert outcome.satisfied is True
    assert outcome.held is True
    assert outcome.revision == 2
    assert outcome.detail == "产物完成", "falls back to the provider detail"
    assert outcome.evidence_ids == ["ev1"]
    assert outcome.artifacts == ["visual"]
    assert outcome.learner_message == "给你"
    assert outcome.tokens_used == 123


def test_success_outcome_incomplete_when_unsatisfied() -> None:
    outcome = policy.success_outcome(
        _task(),
        _resolution(),
        ProviderResult(status="completed"),
        node_id="n1",
        satisfied=False,
        detail="done_when 未满足",
        evidence_ids=[],
        duration_ms=5,
        held=False,
    )
    assert outcome.status == "incomplete"
    assert outcome.satisfied is False
    assert outcome.held is False
    assert outcome.detail == "done_when 未满足"


def test_attempt_outcomes_are_independent_objects() -> None:
    """Retry identity: each attempt gets its own outcome; history never mutates."""

    task = _task()
    first = policy.failure_outcome(
        task, _resolution(), detail="attempt 1 failed", node_id="n1", duration_ms=1
    )
    second = policy.success_outcome(
        task,
        _resolution(),
        ProviderResult(),
        node_id="n1",
        satisfied=True,
        detail="",
        evidence_ids=[],
        duration_ms=2,
        held=False,
    )
    assert first.status == "failed"
    assert second.status == "completed"
    assert first is not second
