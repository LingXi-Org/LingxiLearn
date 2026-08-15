"""Expected learning gain — the deterministic half of the orchestrator's ranking.

Candidate ordering must not be a model's opinion, or "same input, different
profile → different path" becomes luck rather than a property.  These functions
turn a profile row into a per-capability estimate of *how much learning one run
would buy*, so the model only ever reorders a list it did not invent.

Everything here is pure: profile snapshot in, score out.  That is what makes
``tests/test_orchestrator_paths.py`` able to assert path divergence without a
model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .capabilities import Capability

WEAK_MASTERY = 0.45
"""At or below this, a knowledge point is treated as not yet learned."""
STRONG_MASTERY = 0.75
"""At or above this, teaching it again buys very little."""
THIN_EVIDENCE = 2
"""Fewer graded observations than this and the mastery estimate is a guess."""


@dataclass(frozen=True, slots=True)
class ProfileView:
    """The subset of a profile row the scorer reads.

    A plain value object rather than the ORM row, so scoring stays testable
    without a database and cannot accidentally mutate the profile.
    """

    knowledge_point_id: str
    knowledge_point: str = ""
    mastery: float = 0.35
    learning_state: str = "unknown"
    progress: float = 0.0
    confidence: float = 0.0
    evidence_count: int = 0
    misconceptions: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    difficulty: float = 0.5
    review_priority: float = 0.0
    stability: float = 0.0
    review_due_at: datetime | None = None
    last_studied_at: datetime | None = None
    has_lesson_intro: bool = False
    has_deck: bool = False
    has_visual: bool = False
    has_open_quiz: bool = False
    open_questions: int = 0

    @classmethod
    def from_row(cls, row: Any, **extra: Any) -> ProfileView:
        return cls(
            knowledge_point_id=str(getattr(row, "knowledge_point_id", "")),
            knowledge_point=str(getattr(row, "knowledge_point", "") or ""),
            mastery=float(getattr(row, "mastery", 0.35) or 0.0),
            learning_state=str(getattr(row, "learning_state", "unknown") or "unknown"),
            progress=float(getattr(row, "progress", 0.0) or 0.0),
            confidence=float(getattr(row, "confidence", 0.0) or 0.0),
            evidence_count=int(getattr(row, "evidence_count", 0) or 0),
            misconceptions=tuple(str(t) for t in (getattr(row, "misconceptions", ()) or ())),
            prerequisites=tuple(str(t) for t in (getattr(row, "prerequisites", ()) or ())),
            difficulty=float(getattr(row, "difficulty", 0.5) or 0.5),
            review_priority=float(getattr(row, "review_priority", 0.0) or 0.0),
            stability=float(getattr(row, "stability", 0.0) or 0.0),
            review_due_at=getattr(row, "review_due_at", None),
            last_studied_at=getattr(row, "last_studied_at", None),
            **extra,
        )

    @classmethod
    def unseen(cls, knowledge_point_id: str, label: str = "") -> ProfileView:
        """The view for a knowledge point with no profile row yet."""

        return cls(
            knowledge_point_id=knowledge_point_id,
            knowledge_point=label or knowledge_point_id,
            mastery=0.35,
            learning_state="unknown",
            evidence_count=0,
        )

    @property
    def is_weak(self) -> bool:
        return self.mastery <= WEAK_MASTERY

    @property
    def is_strong(self) -> bool:
        return self.mastery >= STRONG_MASTERY

    @property
    def evidence_is_thin(self) -> bool:
        return self.evidence_count < THIN_EVIDENCE

    def is_due(self, now: datetime | None = None) -> bool:
        if self.review_due_at is None:
            return False
        moment = now or datetime.now(UTC)
        due = self.review_due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return moment >= due


@dataclass(frozen=True, slots=True)
class GainEstimate:
    """How much one run of a capability is expected to buy, and why."""

    capability: Capability
    value: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": str(self.capability),
            "value": round(self.value, 4),
            "reason": self.reason,
        }


def _headroom(view: ProfileView) -> float:
    """How much mastery is still available to gain, 0..1."""

    return max(0.0, 1.0 - view.mastery)


def estimate(
    capability: Capability,
    view: ProfileView,
    *,
    prerequisites: tuple[ProfileView, ...] = (),
    now: datetime | None = None,
    requested: bool = False,
) -> GainEstimate:
    """Estimate the learning gain of running ``capability`` on ``view``.

    ``prerequisites`` are the profile views of this point's prerequisites;
    an unmet prerequisite suppresses teaching the target and promotes fixing
    the prerequisite instead.  ``requested`` marks a capability the learner
    explicitly asked for, which raises but never guarantees its ranking.
    """

    weakest_prereq = min(prerequisites, key=lambda p: p.mastery, default=None)
    blocked = weakest_prereq is not None and weakest_prereq.is_weak
    prereq_name = weakest_prereq.knowledge_point if weakest_prereq is not None else ""
    headroom = _headroom(view)
    nudge = 0.15 if requested else 0.0

    match capability:
        case Capability.GRAPH_PREREQUISITE:
            # Worth most when the target is hard and we have not mapped what it
            # rests on; near worthless once prerequisites are known and met.
            if not view.prerequisites and view.mastery < STRONG_MASTERY:
                return _clamp(
                    capability, 0.55 + 0.25 * view.difficulty + nudge, "尚未分析该知识点的前置依赖"
                )
            if blocked:
                return _clamp(capability, 0.45 + nudge, "前置知识薄弱，需要确认依赖顺序")
            return _clamp(capability, 0.12 + nudge, "前置依赖已知且已满足")

        case Capability.CONTENT_LESSON_INTRO:
            if view.has_lesson_intro:
                return _clamp(capability, 0.05 + nudge, "课程引入已存在")
            if blocked:
                return _clamp(
                    capability,
                    0.20 + nudge,
                    f"前置知识「{prereq_name}」尚未掌握，直接引入收益有限",
                )
            return _clamp(
                capability, 0.35 + 0.45 * headroom + nudge, "缺少课程引入，学习者还没有入口"
            )

        case Capability.CONTENT_DECK:
            if view.has_deck:
                return _clamp(capability, 0.05 + nudge, "讲义课件已存在")
            if blocked:
                return _clamp(
                    capability,
                    0.18 + nudge,
                    f"前置知识「{prereq_name}」尚未掌握，先补前置更划算",
                )
            return _clamp(capability, 0.30 + 0.50 * headroom + nudge, "缺少系统讲解材料")

        case Capability.CONTENT_VISUAL:
            if view.has_visual and not requested:
                return _clamp(capability, 0.08, "可视化已存在")
            if blocked:
                return _clamp(
                    capability,
                    0.18 + nudge,
                    f"前置知识「{prereq_name}」尚未掌握，先补前置更划算",
                )
            # Visuals pay off most on hard material the learner is stuck on.
            base = 0.20 + 0.35 * view.difficulty + 0.25 * (1.0 if view.is_weak else 0.0)
            return _clamp(capability, base + nudge, "内容偏抽象，图形化解释有助于建立直觉")

        case Capability.TEACH_EXPLAIN:
            if blocked:
                return _clamp(
                    capability,
                    0.18 + nudge,
                    f"前置知识「{prereq_name}」尚未掌握，讲解会落空",
                )
            if view.misconceptions:
                return _clamp(
                    capability,
                    0.60 + 0.30 * headroom + nudge,
                    f"存在未消解的误区：{'、'.join(view.misconceptions[:2])}",
                )
            if view.open_questions:
                return _clamp(capability, 0.45 + nudge, "学习者有未回答的问题")
            return _clamp(capability, 0.20 + 0.30 * headroom + nudge, "可以补充针对性讲解")

        case Capability.TEACH_STRATEGY:
            if blocked:
                return _clamp(
                    capability,
                    0.20 + nudge,
                    f"前置知识「{prereq_name}」尚未掌握，教学动作收益有限",
                )
            # The default teaching move: always reasonable, never dominant.
            return _clamp(
                capability, 0.30 + 0.30 * headroom + nudge, "根据当前证据选择下一步教学动作"
            )

        case Capability.DIALOG_ANSWER:
            if view.open_questions:
                return _clamp(capability, 0.50 + nudge, "学习者的提问尚未回答")
            return _clamp(capability, 0.15 + nudge, "没有待回答的提问")

        case Capability.ASSESS_GENERATE:
            if view.has_open_quiz:
                return _clamp(capability, 0.05 + nudge, "已有未作答的检测题")
            if blocked:
                # Testing on top of a broken prerequisite produces evidence you
                # could already predict, which is the definition of low information.
                return _clamp(
                    capability,
                    0.15 + nudge,
                    f"前置知识「{prereq_name}」尚未掌握，此时出题信息量很低",
                )
            if view.evidence_is_thin:
                return _clamp(
                    capability, 0.55 + 0.25 * headroom + nudge, "证据太少，掌握度估计不可信"
                )
            if view.is_strong:
                return _clamp(capability, 0.20 + nudge, "掌握度已高，再测收益有限")
            return _clamp(capability, 0.35 + 0.30 * headroom + nudge, "需要新的作答证据")

        case Capability.ASSESS_GRADE:
            return _clamp(
                capability,
                0.70 if view.has_open_quiz else 0.05,
                "有待判分的作答" if view.has_open_quiz else "没有待判分的作答",
            )

        case Capability.ASSESS_INTERPRET:
            if view.evidence_count and view.misconceptions:
                return _clamp(capability, 0.45 + nudge, "作答证据存在模式，需要解读误区")
            return _clamp(capability, 0.15 + nudge, "证据清晰，无需额外解读")

        case Capability.REVIEW_SCHEDULE:
            if view.is_due(now):
                return _clamp(
                    capability, 0.40 + 0.50 * view.review_priority + nudge, "已到复习时间"
                )
            if view.review_priority > 0.6:
                return _clamp(capability, 0.30 + nudge, "复习优先级偏高")
            return _clamp(capability, 0.08 + nudge, "尚未到复习窗口")

        case Capability.MODEL_REFLECT:
            return _clamp(
                capability, 0.25 if view.evidence_count else 0.05, "把最近的学习事件整理进档案"
            )

        case Capability.GRAPH_BUILD:
            return _clamp(capability, 0.20 + nudge, "把本次内容沉淀进知识图谱")

        case Capability.TOOL_INVESTIGATE:
            return _clamp(capability, 0.25 + 0.25 * view.difficulty + nudge, "用确定性工具核查事实")

        case Capability.META_REPORT:
            return _clamp(
                capability,
                0.35 if view.is_strong else 0.10,
                "学习目标基本达成，可以出报告"
                if view.is_strong
                else "学习尚未收敛，出报告为时过早",
            )

        case _:
            return _clamp(capability, 0.10 + nudge, "默认低优先级能力")


def _clamp(capability: Capability, value: float, reason: str) -> GainEstimate:
    return GainEstimate(capability, max(0.0, min(1.0, round(value, 4))), reason)


__all__ = [
    "STRONG_MASTERY",
    "THIN_EVIDENCE",
    "WEAK_MASTERY",
    "GainEstimate",
    "ProfileView",
    "estimate",
]
