"""Shared logic for model-backed brains.

Both providers implement LingxiGraph's ``ChatModel`` protocol, so everything
except construction is identical and lives here.

The prompt deliberately gives the model a **narrow** job: the question, the
hint ladder, the walkthrough and the misconception follow-ups are all authored
in the course pack and handed over verbatim.  The model chooses which one fits
and phrases it naturally.  It is not asked to decide correctness, invent
protocol facts, or pick the hint level — those are computed.

That narrowing is what makes an LLM brain safe to swap in: the kernel's leakage
guard still post-validates the rendered text, and a malformed or missing
response falls back to the authored rung rather than ending the lesson.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from lingxigraph import HumanMessage, SystemMessage

from ..kernel.contracts import CoachContext, ReportContext, TutorMove
from ..kernel.mastery import DEFAULT_PRIOR
from .base import ReportNarrative
from .scripted import ScriptedBrain

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 LingxiLearn 的工科助教，正在带一名本科生完成一次真实的工程分析任务。

铁律：
1. 绝不直接给出答案、结论或最终数值。你的任务是让学生自己得出结论。
2. 只使用提供给你的证据和素材。不要编造帧号、序号、时间或任何技术事实。
3. 一次只问一个问题，简短、具体、指向下一步观察动作。
4. 用中文，语气像坐在学生旁边的助教，不要说教，不要鼓励式空话。

你会拿到课程作者写好的素材：本步骤的问题、分级提示、针对具体误区的追问。
你的工作是**挑选最合适的一条并把它说得自然**，而不是自己发明教学内容。

只输出 JSON，不要 markdown 代码块，格式：
{"intent": "ask|hint|probe_back|confirm", "say": "给学生看的话", "rationale": "你为什么这样问（学生可点开查看）"}"""

REPORT_PROMPT = """你是 LingxiLearn 的工科助教，正在为学生写这次学习的复盘报告。

铁律：
1. 每一条结论都必须基于给定的数据，不要编造。
2. 具体，不要空泛的鼓励。指出他掌握了什么、哪里还薄弱、为什么这样判断。
3. 用中文。

只输出 JSON，不要 markdown 代码块，格式：
{"headline": "一句话总结",
 "strengths": ["..."],
 "gaps": ["..."],
 "next_steps": ["..."]}"""


def _extract_json(text: str) -> dict[str, Any] | None:
    """Tolerate fenced blocks and stray prose around the JSON object."""
    if not text:
        return None
    candidates = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates.append(text)
    brace = re.search(r"\{.*\}", text, re.S)
    if brace:
        candidates.append(brace.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


class LlmBrain:
    """A brain backed by any LingxiGraph ``ChatModel``."""

    name = "llm"

    def __init__(self, model: Any, *, options: dict[str, Any] | None = None) -> None:
        self.model = model
        self.options = options or {}
        self._fallback = ScriptedBrain()

    async def _ask(self, system: str, user: str) -> dict[str, Any] | None:
        try:
            reply = await self.model.agenerate(
                [SystemMessage(system), HumanMessage(user)], **self.options
            )
        except Exception:  # noqa: BLE001 - never let a provider outage end a lesson
            logger.exception("%s brain call failed", self.name)
            return None
        return _extract_json(str(getattr(reply, "content", "") or ""))

    async def next_move(self, ctx: CoachContext) -> TutorMove:
        baseline = await self._fallback.next_move(ctx)
        if ctx.answer_unlocked or baseline.intent == "reveal":
            return baseline  # the walkthrough is authored; do not paraphrase it

        parsed = await self._ask(SYSTEM_PROMPT, _coach_prompt(ctx, baseline))
        if not parsed or not str(parsed.get("say", "")).strip():
            return baseline

        intent = str(parsed.get("intent", baseline.intent))
        if intent not in {"ask", "hint", "probe_back", "confirm"}:
            intent = baseline.intent
        return TutorMove(
            intent=intent,  # type: ignore[arg-type]
            say=str(parsed["say"]).strip(),
            hint_level=baseline.hint_level,  # kernel state, not the model's call
            evidence_ids=list(baseline.evidence_ids),
            expects=baseline.expects,
            choices=list(baseline.choices),
            rationale=str(parsed.get("rationale", baseline.rationale)),
        )

    async def narrate_report(self, ctx: ReportContext) -> ReportNarrative:
        baseline = await self._fallback.narrate_report(ctx)
        parsed = await self._ask(REPORT_PROMPT, _report_prompt(ctx))
        if not parsed or not str(parsed.get("headline", "")).strip():
            return baseline
        return ReportNarrative(
            headline=str(parsed["headline"]).strip(),
            strengths=[str(s) for s in parsed.get("strengths", [])][:5],
            gaps=[str(s) for s in parsed.get("gaps", [])][:5],
            next_steps=[str(s) for s in parsed.get("next_steps", [])][:4],
            # Citations stay computed. A model may phrase a claim; it may not
            # decide which evidence backs it.
            citations=baseline.citations,
        )

    async def aclose(self) -> None:
        closer = getattr(self.model, "aclose", None)
        if callable(closer):
            await closer()


def _coach_prompt(ctx: CoachContext, baseline: TutorMove) -> str:
    evidence_lines = [
        f"- [{e.id}] {e.source}：{e.summary}" for e in ctx.evidence[-8:]
    ] or ["- （本步骤暂无证据）"]
    judgement = ctx.last_judgement
    parts = [
        f"# 任务\n{ctx.mission_title}",
        f"# 当前步骤\n{ctx.step_title}\n目标：{ctx.objective}",
        f"# 课程作者写好的问题\n{ctx.ask}",
        "# 分级提示（第 {} 级适用）\n{}".format(
            ctx.hint_level,
            "\n".join(f"{i}. {h}" for i, h in enumerate(ctx.hint_ladder)) or "（无）",
        ),
        "# 可引用的证据\n" + "\n".join(evidence_lines),
        f"# 学生状态\n已尝试 {ctx.attempts} 次；当前提示级别 {ctx.hint_level}。",
    ]
    if ctx.misconceptions:
        parts.append("# 已识别的误区\n" + "\n".join(f"- {m}" for m in ctx.misconceptions))
    if ctx.misconception_notes:
        parts.append(
            "# 针对这些误区，作者写好的追问\n"
            + "\n".join(f"- {tag}: {note}" for tag, note in ctx.misconception_notes.items())
        )
    if judgement is not None:
        parts.append(
            f"# 上一次作答判定\n{'正确' if judgement.correct else '不正确'}"
            f"（得分 {judgement.score:.2f}）"
        )
    parts.append(
        "# 确定性引擎给出的保底回复（如果你想不出更好的表达，就用它）\n" + baseline.say
    )
    parts.append(
        "现在给出你的下一句话。记住：不要给答案，只问一个问题或给一级提示。"
    )
    return "\n\n".join(parts)


def _report_prompt(ctx: ReportContext) -> str:
    rows = []
    for concept in ctx.concepts:
        before = ctx.mastery_before.get(concept, DEFAULT_PRIOR)
        after = ctx.mastery_after.get(concept, DEFAULT_PRIOR)
        rows.append(f"- {concept}: {before:.0%} → {after:.0%}")
    steps = [
        f"- {r.get('step_id')}: {'通过' if r.get('correct') else '未通过'}，"
        f"尝试 {r.get('attempts')} 次，用到第 {r.get('hint_level')} 级提示"
        for r in ctx.step_results
    ]
    return "\n\n".join(
        [
            f"# 任务\n{ctx.mission_title}",
            f"# 前测 / 后测\n{ctx.probe_score:.0%} → {ctx.verify_score:.0%}",
            "# 概念掌握度变化\n" + ("\n".join(rows) or "（无）"),
            "# 各步骤表现\n" + ("\n".join(steps) or "（无）"),
            "# 仍存在的误区\n" + ("\n".join(f"- {m}" for m in ctx.misconceptions) or "（无）"),
        ]
    )
