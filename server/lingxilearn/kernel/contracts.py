"""Structured contracts exchanged between the kernel, the brains and the UI.

Everything the learner sees is one of these shapes.  Keeping them explicit is
what lets the same teaching kernel drive a packet-forensics mission and a
protocol-simulation mission without either one leaking into the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------

EvidenceKind = Literal["tool_result", "knowledge", "learner_action", "simulation_frame"]


@dataclass(frozen=True, slots=True)
class Evidence:
    """One auditable fact.

    Every teaching claim and every report line must point at evidence ids.  If
    a claim has no evidence, the kernel refuses to state it as fact.
    """

    id: str
    kind: EvidenceKind
    source: str
    """Where it came from, e.g. ``net.pcap.timeline`` or ``rfc9293#sec-3.8.1``."""
    summary: str
    locator: dict[str, Any] = field(default_factory=dict)
    """How to point at it in the UI: ``{"frame": 21, "field": "tcp.seq"}``."""
    value: Any = None
    digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "source": self.source,
            "summary": self.summary,
            "locator": dict(self.locator),
            "value": self.value,
            "digest": self.digest,
        }


# --------------------------------------------------------------------------
# Stage — what the centre of the classroom shows right now
# --------------------------------------------------------------------------

SceneKind = Literal[
    "probe",
    "packet_lab",
    "attribution",
    "sim_console",
    "verify",
    "report",
]


@dataclass(frozen=True, slots=True)
class StageDirective:
    """Which scene the stage renders, and what it highlights.

    This is the "tutor drives the artifact" idea: the coach can point at a
    frame or set a simulator control without generating any markup.
    """

    scene: SceneKind
    props: dict[str, Any] = field(default_factory=dict)
    focus: list[str] = field(default_factory=list)
    """Evidence ids the UI should highlight."""

    def to_dict(self) -> dict[str, Any]:
        return {"scene": self.scene, "props": dict(self.props), "focus": list(self.focus)}


# --------------------------------------------------------------------------
# Coaching
# --------------------------------------------------------------------------

MoveIntent = Literal["ask", "hint", "probe_back", "confirm", "reveal", "wrap"]


@dataclass(frozen=True, slots=True)
class TutorMove:
    """One coaching turn.

    ``hint_level`` is program state, not a suggestion to the model: the kernel
    decides it, and :func:`lingxilearn.kernel.policy.check_leakage` rejects a
    move whose text gives the answer away below the unlocked level.
    """

    intent: MoveIntent
    say: str
    hint_level: int = 0
    evidence_ids: list[str] = field(default_factory=list)
    expects: str = "text"
    """``text`` | ``choice`` | ``attribution`` | ``sim_action`` | ``none``."""
    choices: list[dict[str, Any]] = field(default_factory=list)
    rationale: str = ""
    """Why this move — shown behind the "为什么问这个？" affordance."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "say": self.say,
            "hint_level": self.hint_level,
            "evidence_ids": list(self.evidence_ids),
            "expects": self.expects,
            "choices": list(self.choices),
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class CoachContext:
    """Everything a brain is allowed to see when choosing the next move.

    Note what is supplied rather than invented: the question, the hint ladder,
    the walkthrough and the misconception follow-ups all come from the course
    pack.  A brain chooses *which* authored material fits and phrases it — it
    does not make up protocol facts.  That is what keeps an LLM brain and the
    deterministic brain pedagogically equivalent.
    """

    mission_title: str
    step_id: str
    step_title: str
    objective: str
    concepts: list[str]
    hint_level: int
    answer_unlocked: bool
    attempts: int
    ask: str
    """The authored question for this step."""
    hint_ladder: list[str]
    walkthrough: str
    """Full explanation — only usable once ``answer_unlocked`` is true."""
    misconception_notes: dict[str, str]
    """Misconception tag -> targeted follow-up question."""
    evidence: list[Evidence]
    mastery: dict[str, float]
    misconceptions: list[str]
    last_answer: dict[str, Any] | None
    last_judgement: Judgement | None
    expects: str
    choices: list[dict[str, Any]] = field(default_factory=list)


# --------------------------------------------------------------------------
# Assessment
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Judgement:
    """Result of grading one learner response. Always deterministic first."""

    correct: bool
    score: float
    concept_scores: dict[str, float] = field(default_factory=dict)
    misconceptions: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    feedback: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    """Machine-checkable specifics: which bucket was off, which frame was wrong."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "correct": self.correct,
            "score": self.score,
            "concept_scores": dict(self.concept_scores),
            "misconceptions": list(self.misconceptions),
            "evidence_ids": list(self.evidence_ids),
            "feedback": self.feedback,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True, slots=True)
class ReportContext:
    mission_title: str
    concepts: list[str]
    mastery_before: dict[str, float]
    mastery_after: dict[str, float]
    misconceptions: list[str]
    evidence: list[Evidence]
    step_results: list[dict[str, Any]]
    probe_score: float
    verify_score: float
