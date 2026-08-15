"""Turn what the learner said into a goal. Nothing else.

This is what is left of the old ``global_router`` after its routing authority
was taken away.  It answers *what does the learner want*; it does not answer
*what runs next*.  That second question is recomputed every round by the
orchestrator from the current state, which is the whole point of the refactor.

There is deliberately no ``route`` field anywhere in this module, and
``tests/test_no_fixed_routing.py`` fails the build if one reappears.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

from lingxigraph import HumanMessage, create_agent

from ..agents.contracts import extract_json
from ..agents.model_runtime import agent_model, invoke_agent, message_text
from ..state.session_state import Goal, GoalKind, GoalStack, StackOperation

logger = logging.getLogger(__name__)


class GoalInterpretationUnavailable(RuntimeError):
    """The control-plane model did not return a valid goal."""

GOAL_TYPES = frozenset({"learn", "review", "assess", "ask", "practice", "report", "manage"})

SYSTEM_PROMPT = """你是 LingxiLearn 的目标解析器。

你只回答「学习者想要什么」，绝不回答「接下来跑什么」。不要输出 route、agent、workflow、
next_node 或任何形式的流程决策——下一步由运行时根据学习档案重新计算。

只输出 JSON：
{"goal_type":"learn|review|assess|ask|practice|report|manage",
 "topic":"...","knowledge_points":["..."],"expected_outcome":"可判定的结果",
 "constraints":["..."],"urgency":0.0-1.0,
 "is_interruption":false,"is_correction":false}

规则：
- knowledge_points 优先复用「已知知识点」列表里的 id；没有匹配就留空数组。
- expected_outcome 必须可判定（「能解释 cwnd 如何随丢包变化」而不是「学会 TCP」）；
  写不出可判定的就留空字符串。
- 学习者在学 A 时忽然问 B → is_interruption=true。
- 学习者说「不是这个意思」「我要的是…」纠正上一个目标 → is_correction=true。
- 「给我画个图」是 constraints，不是流程指令。
- urgency 来自学习者的话（「明天考试」→ 高），不是来自主题难度。
不要 Markdown，不要解释。"""


def _clean_goal_type(value: Any) -> str:
    candidate = str(value or "").strip().casefold()
    return candidate if candidate in GOAL_TYPES else "learn"


def _known_points(profile_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "id": str(row.get("knowledge_point_id") or ""),
            "label": str(row.get("knowledge_point") or ""),
        }
        for row in profile_rows
        if row.get("knowledge_point_id")
    ]


def _slugify(topic: str) -> str:
    """A stable id for a topic the profile has never seen.

    Non-ASCII topics keep their text: the id only has to be stable and unique
    per learner, and a transliteration would just make it unreadable.
    """

    collapsed = "-".join(str(topic).strip().split())
    return collapsed[:120] or "unknown-topic"


def build_goal(
    parsed: Mapping[str, Any],
    *,
    utterance: str,
    profile_rows: Sequence[Mapping[str, Any]] = (),
    created_by: str = "goal_interpreter",
) -> Goal:
    """Assemble a validated goal from parsed fields plus the learner's profile.

    Kept separate from the model call so the fallback path and the tests build
    goals through exactly the same code.
    """

    topic = str(parsed.get("topic") or utterance).strip()
    points = [str(p).strip() for p in (parsed.get("knowledge_points") or []) if str(p).strip()]

    if not points:
        # Prefer an existing profile row whose label the learner clearly named,
        # so the same topic does not accumulate one id per phrasing.
        matched = [
            item["id"]
            for item in _known_points(profile_rows)
            if item["label"] and item["label"] in topic
        ]
        points = matched or [_slugify(topic)]

    kind = GoalKind.CURRENT
    if bool(parsed.get("is_interruption")):
        kind = GoalKind.INTERRUPT

    urgency = parsed.get("urgency")
    try:
        urgency = min(1.0, max(0.0, float(urgency)))
    except (TypeError, ValueError):
        urgency = 0.5

    return Goal(
        goal_type=_clean_goal_type(parsed.get("goal_type")),
        topic=topic,
        kind=kind,
        knowledge_points=tuple(dict.fromkeys(points)),
        expected_outcome=str(parsed.get("expected_outcome") or "").strip(),
        constraints=tuple(str(c) for c in (parsed.get("constraints") or []) if str(c).strip()),
        urgency=urgency,
        created_by=created_by,
        raw_utterance=utterance,
    )


async def interpret(
    *,
    utterance: str,
    model: Any | None,
    profile_rows: Sequence[Mapping[str, Any]] = (),
    runtime: Any = None,
    current_goal: Goal | None = None,
) -> Goal:
    """Parse one learner utterance into a goal object."""

    text = str(utterance or "").strip()
    if not text:
        raise ValueError("goal_interpreter requires a non-empty utterance")
    if model is None:
        raise GoalInterpretationUnavailable("目标识别模型不可用")

    payload = {
        "utterance": text,
        "known_knowledge_points": _known_points(profile_rows)[:40],
        "current_goal": current_goal.to_dict() if current_goal else None,
    }
    try:
        agent = create_agent(
            agent_model(model, "goal_interpreter"),
            system_prompt=SYSTEM_PROMPT,
            name="goal-interpreter",
        )
        result = await invoke_agent(
            agent,
            HumanMessage(json.dumps(payload, ensure_ascii=False)),
            runtime,
            agent_name="goal_interpreter",
            recursion_limit=4,
        )
        parsed = extract_json(message_text(result)) or {}
    except Exception as exc:  # noqa: BLE001 - do not route with local heuristics
        logger.exception("goal interpretation failed")
        raise GoalInterpretationUnavailable("目标识别模型执行失败") from exc

    if not parsed:
        raise GoalInterpretationUnavailable("目标识别模型没有返回有效结果")
    # A model that tries to route anyway is answering a question it was not
    # asked. Drop the field rather than letting it reach the orchestrator.
    for forbidden in ("route", "agent", "workflow", "next_node"):
        parsed.pop(forbidden, None)

    goal = build_goal(parsed, utterance=text, profile_rows=profile_rows)
    if bool(parsed.get("is_correction")):
        # A correction replaces the current goal rather than stacking on it.
        return goal
    return goal


def apply_to_stack(
    stack: GoalStack, goal: Goal, *, is_correction: bool = False
) -> StackOperation:
    """Push, replace, or seed the stack, and return the undo record.

    An interruption stacks (the learner will come back to what they were doing);
    a correction replaces (they will not).
    """

    if is_correction and stack.current() is not None:
        return stack.replace(goal, reason=f"纠偏：{goal.raw_utterance[:60]}")
    if goal.kind is GoalKind.INTERRUPT and stack.current() is not None:
        return stack.push(goal, reason=f"打断：{goal.raw_utterance[:60]}")
    if stack.current() is None:
        return stack.push(goal, reason=f"新目标：{goal.raw_utterance[:60]}")
    return stack.replace(goal, reason=f"切换目标：{goal.raw_utterance[:60]}")


__all__ = [
    "GOAL_TYPES",
    "GoalInterpretationUnavailable",
    "SYSTEM_PROMPT",
    "apply_to_stack",
    "build_goal",
    "interpret",
]
