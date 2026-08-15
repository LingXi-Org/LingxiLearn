"""Course-pack data model.

A pack is the *only* place a subject lives.  Computer Networks ships first;
数据结构 / 操作系统 / 组成原理 are new directories, not kernel changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Concept:
    id: str
    title: str
    requires: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass(frozen=True, slots=True)
class Misconception:
    id: str
    title: str
    concept: str
    note: str = ""
    """The targeted follow-up question a coach asks when this tag fires."""


@dataclass(frozen=True, slots=True)
class Artifact:
    id: str
    kind: str
    path: Path
    title: str = ""
    source: str = "synthetic"
    license: str = "CC0-1.0"


@dataclass(frozen=True, slots=True)
class ToolCall:
    call: str
    args: dict[str, Any] = field(default_factory=dict)
    as_: str = ""
    summary: str = ""


@dataclass(frozen=True, slots=True)
class Item:
    """A gradeable question used in the pre-test or the post-test."""

    id: str
    concept: str
    prompt: str
    expects: str = "choice"
    choices: list[dict[str, Any]] = field(default_factory=list)
    grader: dict[str, Any] = field(default_factory=dict)
    explain: str = ""
    difficulty: int = 1


@dataclass(frozen=True, slots=True)
class Step:
    id: str
    title: str
    objective: str
    concepts: list[str]
    scene: str
    ask: str
    expects: str = "text"
    choices: list[dict[str, Any]] = field(default_factory=list)
    tools: list[ToolCall] = field(default_factory=list)
    grader: dict[str, Any] = field(default_factory=dict)
    hint_ladder: list[str] = field(default_factory=list)
    walkthrough: str = ""
    leak_guard: dict[str, Any] = field(default_factory=dict)
    reveal_after: int = 3
    max_attempts: int = 4
    stage_props: dict[str, Any] = field(default_factory=dict)
    knowledge: list[str] = field(default_factory=list)
    """Knowledge-base queries to run alongside the tools, for citations."""
    skip_if_mastered: float = 0.0
    """Skip this step when every concept is already at or above this mastery.

    Steps stay in authored order (later steps often depend on earlier tool
    output), so personalisation happens by *dropping* warm-ups the learner has
    demonstrably outgrown rather than by reshuffling a sequence.
    """

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "objective": self.objective,
            "concepts": list(self.concepts),
            "scene": self.scene,
            "ask": self.ask,
            "expects": self.expects,
            "choices": list(self.choices),
            "tools": [{"call": t.call, "args": dict(t.args), "as": t.as_} for t in self.tools],
            "grader": dict(self.grader),
            "hint_ladder": list(self.hint_ladder),
            "walkthrough": self.walkthrough,
            "leak_guard": dict(self.leak_guard),
            "reveal_after": self.reveal_after,
            "max_attempts": self.max_attempts,
            "stage_props": dict(self.stage_props),
            "knowledge": list(self.knowledge),
        }


@dataclass(frozen=True, slots=True)
class Mission:
    id: str
    title: str
    subtitle: str
    summary: str
    concepts: list[str]
    steps: list[Step]
    probe: list[Item] = field(default_factory=list)
    verify: list[Item] = field(default_factory=list)
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    why_not_chat: str = ""
    """One line on what this task needs that a chat window cannot provide."""
    estimated_minutes: int = 15

    def step(self, step_id: str) -> Step | None:
        return next((s for s in self.steps if s.id == step_id), None)


@dataclass(frozen=True, slots=True)
class Pack:
    id: str
    title: str
    version: str
    description: str
    root: Path
    concepts: dict[str, Concept]
    misconceptions: dict[str, Misconception]
    missions: dict[str, Mission]

    @property
    def checkpoint_ns(self) -> str:
        """Content version namespaces the checkpoints.

        Publishing new lesson content therefore cannot reinterpret a session
        that is already in flight.
        """
        return f"pack/{self.id}@{self.version}"

    def misconception_notes(self, tags: list[str]) -> dict[str, str]:
        return {t: self.misconceptions[t].note for t in tags if t in self.misconceptions}


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Stable machine-readable codes so tests assert on codes, not prose."""

    path: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def codes(self) -> set[str]:
        return {i.code for i in self.issues}
