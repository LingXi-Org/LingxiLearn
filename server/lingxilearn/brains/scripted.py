"""Deterministic tutor brain.

Selects and phrases authored material by rule.  No network, no key, no
sampling — so the teaching loop is fully runnable offline, unit tests assert on
exact strings, and the evaluation harness is reproducible run to run.

It is also the safety floor: when an LLM brain produces a move that trips the
leakage guard, the kernel falls back to this brain's output for that turn.
"""

from __future__ import annotations

from ..kernel.contracts import CoachContext, ReportContext, TutorMove
from ..kernel.mastery import DEFAULT_PRIOR
from .base import ReportNarrative

_ENCOURAGE = "先别急着给结论——把证据摆出来，再下判断。"


class ScriptedBrain:
    name = "scripted"

    async def next_move(self, ctx: CoachContext) -> TutorMove:
        # The learner earned the walkthrough: they tried enough and asked for it.
        if ctx.answer_unlocked and ctx.walkthrough:
            return TutorMove(
                intent="reveal",
                say=ctx.walkthrough,
                hint_level=ctx.hint_level,
                evidence_ids=[e.id for e in ctx.evidence[:4]],
                expects="none",
                rationale="你已经做过足够的尝试并主动要求复盘，现在给出完整推理。",
            )

        judgement = ctx.last_judgement

        # First contact with this step — ask the authored question.
        if judgement is None:
            return TutorMove(
                intent="ask",
                say=ctx.ask or f"针对「{ctx.step_title}」，你的判断是什么？",
                hint_level=0,
                evidence_ids=[e.id for e in ctx.evidence[:3]],
                expects=ctx.expects,
                choices=list(ctx.choices),
                rationale=ctx.objective,
            )

        if judgement.correct:
            return TutorMove(
                intent="confirm",
                say=judgement.feedback or "对了。你的依据和数据是一致的。",
                hint_level=ctx.hint_level,
                evidence_ids=list(judgement.evidence_ids),
                expects="none",
                rationale="判定通过，进入下一步。",
            )

        # Wrong answer. Prefer a follow-up aimed at the specific misconception;
        # otherwise walk one rung up the authored hint ladder.
        for tag in judgement.misconceptions:
            note = ctx.misconception_notes.get(tag)
            if note:
                return TutorMove(
                    intent="probe_back",
                    say=note,
                    hint_level=ctx.hint_level,
                    evidence_ids=list(judgement.evidence_ids),
                    expects=ctx.expects,
                    choices=list(ctx.choices),
                    rationale=f"检测到具体误区：{tag}",
                )

        ladder = ctx.hint_ladder or [_ENCOURAGE]
        return TutorMove(
            intent="hint",
            say=ladder[min(ctx.hint_level, len(ladder) - 1)],
            hint_level=ctx.hint_level,
            evidence_ids=list(judgement.evidence_ids) or [e.id for e in ctx.evidence[:2]],
            expects=ctx.expects,
            choices=list(ctx.choices),
            rationale=f"第 {ctx.attempts} 次尝试未通过，给到第 {ctx.hint_level} 级提示。",
        )

    async def narrate_report(self, ctx: ReportContext) -> ReportNarrative:
        strengths: list[str] = []
        gaps: list[str] = []
        citations: dict[str, list[str]] = {}
        evidence_ids = [e.id for e in ctx.evidence]

        for concept in ctx.concepts:
            before = ctx.mastery_before.get(concept, DEFAULT_PRIOR)
            after = ctx.mastery_after.get(concept, DEFAULT_PRIOR)
            delta = after - before
            label = f"{concept}：{before:.0%} → {after:.0%}"
            if after >= 0.7:
                claim = f"{label}，本轮判断与数据一致。"
                strengths.append(claim)
            elif delta > 0.02:
                claim = f"{label}，有进步但还不稳。"
                gaps.append(claim)
            else:
                claim = f"{label}，仍是薄弱点。"
                gaps.append(claim)
            supporting = [
                r.get("evidence_ids", []) for r in ctx.step_results if concept in r.get("concepts", [])
            ]
            flat = [i for group in supporting for i in group] or evidence_ids[:2]
            citations[claim] = flat

        for tag in ctx.misconceptions:
            claim = f"仍存在的误区：{tag}"
            gaps.append(claim)
            citations[claim] = [
                r["evidence_ids"][0]
                for r in ctx.step_results
                if tag in r.get("misconceptions", []) and r.get("evidence_ids")
            ][:2] or evidence_ids[:1]

        gain = ctx.verify_score - ctx.probe_score
        headline = (
            f"「{ctx.mission_title}」完成。前测 {ctx.probe_score:.0%}，"
            f"后测 {ctx.verify_score:.0%}，净提升 {gain:+.0%}。"
        )

        next_steps = [f"针对 {tag} 做一次 5 分钟微练习。" for tag in ctx.misconceptions[:2]]
        if not next_steps:
            weakest = min(
                ctx.concepts,
                key=lambda c: ctx.mastery_after.get(c, DEFAULT_PRIOR),
                default="",
            )
            if weakest:
                next_steps = [f"下一次从 {weakest} 的迁移练习开始。"]

        return ReportNarrative(
            headline=headline,
            strengths=strengths,
            gaps=gaps,
            next_steps=next_steps,
            citations=citations,
        )

    async def aclose(self) -> None:  # nothing to release
        return None
