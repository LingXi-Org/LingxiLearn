"""The capability vocabulary.

The orchestrator plans in *capabilities*, never in agent names.  This module is
the closed vocabulary those plans are written in: a skill declares which
capabilities it provides, the orchestrator asks for a capability, and
``runtime.dispatch`` resolves the pairing at run time through
``skill_registry``.

Keeping the vocabulary closed is what stops "capability" from quietly becoming
a second name for an agent — an unregistered tag is a hard error, not a new
implicit route.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Capability(StrEnum):
    """Every capability the runtime is allowed to plan for."""

    # --- understanding the learner ----------------------------------------
    MODEL_REFLECT = "model.reflect"
    GRAPH_BUILD = "graph.build"
    GRAPH_PREREQUISITE = "graph.prerequisite"
    REVIEW_SCHEDULE = "review.schedule"

    # --- producing material ------------------------------------------------
    CONTENT_LESSON_INTRO = "content.lesson_intro"
    CONTENT_DECK = "content.deck"
    CONTENT_VISUAL = "content.visual"

    # --- teaching ----------------------------------------------------------
    TEACH_STRATEGY = "teach.strategy"
    TEACH_EXPLAIN = "teach.explain"
    DIALOG_ANSWER = "dialog.answer"
    DIALOG_NEGOTIATE = "dialog.negotiate"
    DIALOG_CONVERSE = "dialog.converse"
    DIALOG_INTERVIEW = "dialog.interview"
    DIALOG_PROBE = "dialog.probe"
    PLAN_PRESENT = "plan.present"

    # --- assessing ---------------------------------------------------------
    ASSESS_GENERATE = "assess.generate"
    ASSESS_GRADE = "assess.grade"
    ASSESS_INTERPRET = "assess.interpret"

    # --- investigation and reporting ---------------------------------------
    TOOL_INVESTIGATE = "tool.investigate"
    META_REPORT = "meta.report"
    META_EVALUATE = "meta.evaluate"
    META_AUTHOR_SKILL = "meta.author_skill"


@dataclass(frozen=True, slots=True)
class CapabilityInfo:
    """What the runtime needs to know about a capability without running it."""

    capability: Capability
    label: str
    """Learner-facing Simplified Chinese label, used in ``next_step`` entries."""
    learner_facing: bool
    """True when running it produces something the learner directly sees."""
    heavy_artifact: bool
    """True when one run produces an expensive artifact; counted by guardrails."""
    irreversible: bool
    """True when running it has effects outside the run; needs confirmation."""
    conversational: bool = False
    opening_conversation: bool = False
    turn_complete: bool = False
    """True when this capability's output can finish the current user turn."""


CAPABILITY_INFO: dict[Capability, CapabilityInfo] = {
    Capability.MODEL_REFLECT: CapabilityInfo(
        Capability.MODEL_REFLECT, "整理学习状态", False, False, False
    ),
    Capability.GRAPH_BUILD: CapabilityInfo(
        Capability.GRAPH_BUILD, "构建知识图谱", False, False, True
    ),
    Capability.GRAPH_PREREQUISITE: CapabilityInfo(
        Capability.GRAPH_PREREQUISITE, "分析前置知识", False, False, False
    ),
    Capability.REVIEW_SCHEDULE: CapabilityInfo(
        Capability.REVIEW_SCHEDULE, "安排复习", False, False, False
    ),
    Capability.CONTENT_LESSON_INTRO: CapabilityInfo(
        Capability.CONTENT_LESSON_INTRO, "生成课程引入", True, True, False
    ),
    Capability.CONTENT_DECK: CapabilityInfo(
        Capability.CONTENT_DECK, "生成讲义课件", True, True, False
    ),
    Capability.CONTENT_VISUAL: CapabilityInfo(
        Capability.CONTENT_VISUAL, "生成可视化讲解", True, True, False
    ),
    Capability.TEACH_STRATEGY: CapabilityInfo(
        Capability.TEACH_STRATEGY, "选择教学策略", True, False, False
    ),
    Capability.TEACH_EXPLAIN: CapabilityInfo(
        Capability.TEACH_EXPLAIN, "针对性讲解", True, False, False, turn_complete=True
    ),
    Capability.DIALOG_ANSWER: CapabilityInfo(
        Capability.DIALOG_ANSWER, "回答追问", True, False, False, turn_complete=True
    ),
    Capability.DIALOG_NEGOTIATE: CapabilityInfo(
        Capability.DIALOG_NEGOTIATE, "与学习者协商", True, False, False
    ),
    Capability.DIALOG_CONVERSE: CapabilityInfo(
        Capability.DIALOG_CONVERSE,
        "回应你的消息",
        True,
        False,
        False,
        True,
        False,
        True,
    ),
    Capability.DIALOG_INTERVIEW: CapabilityInfo(
        Capability.DIALOG_INTERVIEW,
        "了解你的基础",
        True,
        False,
        False,
        True,
        True,
        True,
    ),
    Capability.DIALOG_PROBE: CapabilityInfo(
        Capability.DIALOG_PROBE, "向你确认理解", True, False, False, turn_complete=True
    ),
    Capability.PLAN_PRESENT: CapabilityInfo(
        Capability.PLAN_PRESENT, "更新执行计划", True, False, False
    ),
    Capability.ASSESS_GENERATE: CapabilityInfo(
        Capability.ASSESS_GENERATE, "出题检测", True, False, False
    ),
    Capability.ASSESS_GRADE: CapabilityInfo(Capability.ASSESS_GRADE, "判分", False, False, False),
    Capability.ASSESS_INTERPRET: CapabilityInfo(
        Capability.ASSESS_INTERPRET, "解读作答证据", False, False, False
    ),
    Capability.TOOL_INVESTIGATE: CapabilityInfo(
        Capability.TOOL_INVESTIGATE, "用工具核查", False, False, False
    ),
    Capability.META_REPORT: CapabilityInfo(
        Capability.META_REPORT, "生成学习报告", True, False, False
    ),
    Capability.META_EVALUATE: CapabilityInfo(
        Capability.META_EVALUATE, "评测技能", False, False, False
    ),
    Capability.META_AUTHOR_SKILL: CapabilityInfo(
        Capability.META_AUTHOR_SKILL, "起草新能力", False, False, True
    ),
}


class UnknownCapability(ValueError):
    """A plan referenced a capability outside the closed vocabulary."""


def parse(value: str) -> Capability:
    """Resolve a capability tag, refusing anything outside the vocabulary."""

    try:
        return Capability(str(value).strip())
    except ValueError:
        raise UnknownCapability(f"unknown capability: {value!r}") from None


def info(value: str | Capability) -> CapabilityInfo:
    capability = value if isinstance(value, Capability) else parse(value)
    return CAPABILITY_INFO[capability]


def all_tags() -> tuple[str, ...]:
    return tuple(sorted(item.value for item in Capability))


__all__ = [
    "CAPABILITY_INFO",
    "Capability",
    "CapabilityInfo",
    "UnknownCapability",
    "all_tags",
    "info",
    "parse",
]
