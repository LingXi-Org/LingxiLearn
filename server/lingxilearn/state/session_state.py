"""The goal stack and the run state machine.

Two things live here, and they are the reason routing is revocable:

* :class:`GoalStack` — bottom-up long-term → current → interrupt goals, with
  ``push`` / ``pop`` / ``replace`` returning an explicit before/after pair that
  the repository writes to ``session_state_events``.  Undoing a routing decision
  is replaying the stack to the snapshot before an event, not guessing.
* :class:`RuntimeStatus` — the loop's phase, with a closed transition table so a
  node cannot leave the run in a state the loop has no edge for.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class RuntimeStatus(StrEnum):
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    OBSERVING = "OBSERVING"
    UPDATING = "UPDATING"
    REPLANNING = "REPLANNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


TERMINAL_STATUSES = frozenset({RuntimeStatus.COMPLETED, RuntimeStatus.FAILED})

_TRANSITIONS: dict[RuntimeStatus, frozenset[RuntimeStatus]] = {
    RuntimeStatus.PLANNING: frozenset(
        {
            RuntimeStatus.EXECUTING,
            RuntimeStatus.WAITING_FOR_USER,
            RuntimeStatus.COMPLETED,
            RuntimeStatus.FAILED,
        }
    ),
    RuntimeStatus.EXECUTING: frozenset(
        {
            RuntimeStatus.OBSERVING,
            RuntimeStatus.WAITING_FOR_USER,
            RuntimeStatus.FAILED,
        }
    ),
    RuntimeStatus.OBSERVING: frozenset({RuntimeStatus.UPDATING, RuntimeStatus.FAILED}),
    RuntimeStatus.UPDATING: frozenset(
        {
            RuntimeStatus.REPLANNING,
            RuntimeStatus.WAITING_FOR_USER,
            RuntimeStatus.COMPLETED,
            RuntimeStatus.FAILED,
        }
    ),
    RuntimeStatus.REPLANNING: frozenset(
        {
            RuntimeStatus.PLANNING,
            RuntimeStatus.WAITING_FOR_USER,
            RuntimeStatus.COMPLETED,
            RuntimeStatus.FAILED,
        }
    ),
    RuntimeStatus.WAITING_FOR_USER: frozenset(
        {RuntimeStatus.PLANNING, RuntimeStatus.COMPLETED, RuntimeStatus.FAILED}
    ),
    RuntimeStatus.COMPLETED: frozenset(),
    RuntimeStatus.FAILED: frozenset(),
}


class IllegalTransition(ValueError):
    """A node tried to move the run into a state the loop has no edge for."""


def transition(current: RuntimeStatus | str, target: RuntimeStatus | str) -> RuntimeStatus:
    """Validate and return the next runtime status."""

    source = RuntimeStatus(str(current))
    destination = RuntimeStatus(str(target))
    if destination is source:
        return destination
    if destination not in _TRANSITIONS[source]:
        raise IllegalTransition(f"{source} cannot transition to {destination}")
    return destination


class GoalKind(StrEnum):
    LONG_TERM = "long_term"
    CURRENT = "current"
    INTERRUPT = "interrupt"


class GoalStatus(StrEnum):
    OPEN = "open"
    SATISFIED = "satisfied"
    ABANDONED = "abandoned"


@dataclass(frozen=True, slots=True)
class Goal:
    """What the learner is trying to achieve. Carries no execution plan."""

    goal_type: str
    topic: str
    id: str = field(default_factory=lambda: f"goal_{uuid4().hex[:12]}")
    kind: GoalKind = GoalKind.CURRENT
    knowledge_points: tuple[str, ...] = ()
    expected_outcome: str = ""
    constraints: tuple[str, ...] = ()
    urgency: float = 0.5
    status: GoalStatus = GoalStatus.OPEN
    satisfied_when: dict[str, Any] = field(default_factory=dict)
    created_by: str = "goal_interpreter"
    raw_utterance: str = ""
    pushed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": str(self.kind),
            "goal_type": self.goal_type,
            "topic": self.topic,
            "knowledge_points": list(self.knowledge_points),
            "expected_outcome": self.expected_outcome,
            "constraints": list(self.constraints),
            "urgency": float(self.urgency),
            "status": str(self.status),
            "satisfied_when": dict(self.satisfied_when),
            "created_by": self.created_by,
            "raw_utterance": self.raw_utterance,
            "pushed_at": self.pushed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Goal:
        pushed = value.get("pushed_at")
        return cls(
            id=str(value.get("id") or f"goal_{uuid4().hex[:12]}"),
            kind=GoalKind(str(value.get("kind") or GoalKind.CURRENT)),
            goal_type=str(value.get("goal_type") or "learn"),
            topic=str(value.get("topic") or ""),
            knowledge_points=tuple(str(k) for k in value.get("knowledge_points") or ()),
            expected_outcome=str(value.get("expected_outcome") or ""),
            constraints=tuple(str(c) for c in value.get("constraints") or ()),
            urgency=float(value.get("urgency") or 0.5),
            status=GoalStatus(str(value.get("status") or GoalStatus.OPEN)),
            satisfied_when=dict(value.get("satisfied_when") or {}),
            created_by=str(value.get("created_by") or "goal_interpreter"),
            raw_utterance=str(value.get("raw_utterance") or ""),
            pushed_at=datetime.fromisoformat(pushed)
            if isinstance(pushed, str) and pushed
            else datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class StackOperation:
    """What changed, in a form the undo log can store verbatim."""

    op: str
    before: list[dict[str, Any]]
    after: list[dict[str, Any]]
    reason: str = ""

    @property
    def changed(self) -> bool:
        return self.before != self.after


class GoalStack:
    """Bottom-up goal stack. Every mutation returns its own undo record."""

    def __init__(self, goals: list[dict[str, Any]] | None = None) -> None:
        self._goals: list[Goal] = [Goal.from_dict(item) for item in (goals or [])]

    # -- reads ---------------------------------------------------------------

    @property
    def goals(self) -> list[Goal]:
        return list(self._goals)

    def to_list(self) -> list[dict[str, Any]]:
        return [goal.to_dict() for goal in self._goals]

    def current(self) -> Goal | None:
        """The goal the runtime is actually working on: the topmost open one."""

        for goal in reversed(self._goals):
            if goal.status is GoalStatus.OPEN:
                return goal
        return None

    def long_term(self) -> Goal | None:
        return next((g for g in self._goals if g.kind is GoalKind.LONG_TERM), None)

    def is_empty(self) -> bool:
        return not any(goal.status is GoalStatus.OPEN for goal in self._goals)

    # -- mutations -----------------------------------------------------------

    def push(self, goal: Goal, *, reason: str = "") -> StackOperation:
        """Interrupt: the new goal becomes current without discarding the old one."""

        before = self.to_list()
        self._goals.append(goal)
        return StackOperation("push", before, self.to_list(), reason)

    def pop(self, *, reason: str = "", goal_id: str | None = None) -> StackOperation:
        """Achieved: mark the goal satisfied and fall back to the one beneath."""

        before = self.to_list()
        target = (
            next((g for g in self._goals if g.id == goal_id), None) if goal_id else self.current()
        )
        if target is not None:
            index = self._goals.index(target)
            self._goals[index] = replace(target, status=GoalStatus.SATISFIED)
        return StackOperation("pop", before, self.to_list(), reason)

    def replace(self, goal: Goal, *, reason: str = "") -> StackOperation:
        """Correction: the current goal was wrong, swap it rather than stack on it."""

        before = self.to_list()
        target = self.current()
        if target is None:
            self._goals.append(goal)
        else:
            index = self._goals.index(target)
            self._goals[index] = replace(
                goal, id=goal.id, kind=target.kind, pushed_at=goal.pushed_at
            )
        return StackOperation("replace", before, self.to_list(), reason)

    def abandon(self, *, reason: str = "") -> StackOperation:
        before = self.to_list()
        target = self.current()
        if target is not None:
            index = self._goals.index(target)
            self._goals[index] = replace(target, status=GoalStatus.ABANDONED)
        return StackOperation("abandon", before, self.to_list(), reason)


DEFAULT_BUDGET: dict[str, Any] = {
    "steps_used": 0,
    "max_steps": 24,
    "replans_used": 0,
    "max_replans": 6,
    "tokens_used": 0,
    "token_budget": 400_000,
    "wall_ms_used": 0,
    "wall_ms_budget": 1_800_000,
    "heavy_artifacts_used": 0,
    "max_heavy_artifacts": 6,
    "forged_skills_used": 0,
    "max_forged_skills": 1,
}


def new_budget(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    budget = dict(DEFAULT_BUDGET)
    budget.update(overrides or {})
    return budget


__all__ = [
    "DEFAULT_BUDGET",
    "Goal",
    "GoalKind",
    "GoalStack",
    "GoalStatus",
    "IllegalTransition",
    "RuntimeStatus",
    "StackOperation",
    "TERMINAL_STATUSES",
    "new_budget",
    "transition",
]
