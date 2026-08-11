"""The tutor brain seam.

A brain decides *how to say* the next coaching turn.  It never decides whether
the learner was right (that is deterministic grading), never invents protocol
facts (those come from tools and the knowledge base), and never controls the
hint level (that is kernel state).  Narrowing the model's job this way is what
makes the deterministic brain a genuine peer of the LLM ones rather than a
degraded stub.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..kernel.contracts import CoachContext, ReportContext, TutorMove


@dataclass(frozen=True, slots=True)
class ReportNarrative:
    """Prose for the learning report. Every claim must cite ledger evidence."""

    headline: str
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    citations: dict[str, list[str]] = field(default_factory=dict)
    """Claim text -> evidence ids backing it."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "strengths": list(self.strengths),
            "gaps": list(self.gaps),
            "next_steps": list(self.next_steps),
            "citations": {k: list(v) for k, v in self.citations.items()},
        }


@runtime_checkable
class TutorBrain(Protocol):
    name: str

    async def next_move(self, ctx: CoachContext) -> TutorMove: ...

    async def narrate_report(self, ctx: ReportContext) -> ReportNarrative: ...

    async def aclose(self) -> None: ...
