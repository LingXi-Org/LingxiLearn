"""The tutoring kernel: a domain-agnostic LingxiGraph StateGraph.

Read the node names top to bottom and you get the product thesis:

    intake → diagnose → plan → investigate → coach → await_learner
           → judge → advance → verify → report

Understand the learner, run real tools on the real artefact, coach without
giving it away, check whether they actually got it, and leave evidence behind.
Not one node mentions DNS, TCP or packets — the subject arrives through the
course pack and the tool registry, which is what lets 数据结构 / 操作系统 /
组成原理 ship later as content rather than as a rewrite.

**Invariant worth knowing before editing:** a node that calls ``interrupt()``
re-executes from the top when the run resumes.  So nothing before an
``interrupt()`` may emit a stream event or mutate anything outside the returned
state delta, or the learner sees it twice on every resume.
"""

from __future__ import annotations

import logging
from typing import Any

from lingxigraph import END, START, Runtime, StateGraph, interrupt

from ..brains.base import TutorBrain
from ..packs.models import Item, Mission, Pack, Step
from ..tools.registry import ToolRegistry
from . import mastery as mastery_model
from .contracts import CoachContext, Judgement, ReportContext, StageDirective, TutorMove
from .evidence import Ledger, verify_citations
from .graders import grade
from .policy import (
    LeakGuard,
    check_leakage,
    fallback_hint,
    next_hint_level,
    should_unlock_answer,
)
from .state import TutorContext, TutorState

logger = logging.getLogger(__name__)

STREAM_CHANNEL = "tutor"
"""Domain events ride LingxiGraph's CUSTOM channel under this name."""


def emit(runtime: Runtime[Any] | None, kind: str, **payload: Any) -> None:
    """Publish a teaching event. Safe to call when no runtime is attached."""
    if runtime is None:
        return
    try:
        runtime.emit(STREAM_CHANNEL, {"type": kind, **payload})
    except Exception:  # noqa: BLE001 - telemetry must never break teaching
        logger.debug("failed to emit %s", kind, exc_info=True)


def public_item(item: Item) -> dict[str, Any]:
    """The learner-facing shape of a question — never includes the answer key."""
    return {
        "id": item.id,
        "concept": item.concept,
        "prompt": item.prompt,
        "expects": item.expects,
        "choices": list(item.choices),
        "difficulty": item.difficulty,
    }


class TutoringKernel:
    """Builds the graph. One instance per (pack, brain) pair."""

    def __init__(self, *, pack: Pack, brain: TutorBrain, registry: ToolRegistry) -> None:
        self.pack = pack
        self.brain = brain
        self.registry = registry

    # -- helpers ---------------------------------------------------------

    def _mission(self, state: TutorState) -> Mission:
        mission = self.pack.missions.get(str(state.get("mission_id", "")))
        if mission is None:
            raise KeyError(f"unknown mission: {state.get('mission_id')}")
        return mission

    def _current_step(self, state: TutorState) -> Step | None:
        mission = self._mission(state)
        plan = list(state.get("plan") or [])
        index = int(state.get("step_index", 0))
        if index >= len(plan):
            return None
        return mission.step(plan[index])

    def _grade_items(
        self, items: list[Item], answers: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], float, dict[str, float], list[str]]:
        records: list[dict[str, Any]] = []
        concept_scores: dict[str, float] = {}
        tags: list[str] = []
        for item in items:
            spec = {**item.grader, "concepts": [item.concept]}
            judgement = grade(spec, answers.get(item.id))
            records.append(
                {
                    "item_id": item.id,
                    "concept": item.concept,
                    "answer": answers.get(item.id),
                    **judgement.to_dict(),
                }
            )
            prior = concept_scores.get(item.concept)
            concept_scores[item.concept] = (
                judgement.score if prior is None else (prior + judgement.score) / 2
            )
            for tag in judgement.misconceptions:
                if tag not in tags:
                    tags.append(tag)
        overall = sum(r["score"] for r in records) / len(records) if records else 0.0
        return records, overall, concept_scores, tags

    # -- nodes -----------------------------------------------------------

    async def intake(self, state: TutorState, runtime: Runtime[TutorContext]) -> dict[str, Any]:
        mission = self._mission(state)
        ledger = Ledger(list(state.get("evidence") or []))
        ledger.add(
            kind="learner_action",
            source="session.start",
            summary=f"开始任务：{mission.title}",
            locator={"mission": mission.id},
            value={"concepts": mission.concepts},
        )
        emit(
            runtime,
            "stage.changed",
            stage={"scene": "probe", "props": {"mission": mission.id}, "focus": []},
            phase="diagnose",
        )
        return {
            "mission_title": mission.title,
            "phase": "diagnose",
            "evidence": ledger.delta(),
            "stage": StageDirective(scene="probe", props={"mission": mission.id}).to_dict(),
        }

    async def diagnose(self, state: TutorState, runtime: Runtime[TutorContext]) -> dict[str, Any]:
        """Pre-test. Pauses for the learner, then grades deterministically."""
        mission = self._mission(state)
        answers = interrupt(
            {
                "kind": "probe",
                "title": "开始前，先花一分钟看看你现在在哪",
                "items": [public_item(i) for i in mission.probe],
                "stage": StageDirective(
                    scene="probe", props={"mission": mission.id}
                ).to_dict(),
            }
        )
        # --- everything below runs only after resume -----------------------
        answers = answers if isinstance(answers, dict) else {}
        records, overall, concept_scores, tags = self._grade_items(mission.probe, answers)

        ledger = Ledger(list(state.get("evidence") or []))
        for record in records:
            ledger.add(
                kind="learner_action",
                source=f"probe.{record['item_id']}",
                summary=f"前测 {record['item_id']}：{'对' if record['correct'] else '错'}",
                locator={"item": record["item_id"], "concept": record["concept"]},
                value={"answer": record["answer"], "score": record["score"]},
            )
        evidence_delta = ledger.delta()
        seeded, changes = mastery_model.apply(
            dict(state.get("mastery") or {}),
            concept_scores,
            hint_level=0,
            evidence_ids=[e["id"] for e in evidence_delta],
            counts={
                concept: int(count)
                for concept, count in dict(state.get("mastery_counts") or {}).items()
            },
            reason="前测结果",
        )

        emit(runtime, "probe.graded", score=overall, concepts=concept_scores, misconceptions=tags)
        emit(runtime, "mastery.updated", changes=[c.to_dict() for c in changes])

        return {
            "phase": "plan",
            "probe_results": records,
            "probe_score": round(overall, 4),
            "mastery": seeded,
            "mastery_before": seeded,
            "mastery_counts": {c: 1.0 for c in concept_scores},
            "mastery_changes": [c.to_dict() for c in changes],
            "misconceptions": tags,
            "evidence": evidence_delta,
        }

    async def plan(self, state: TutorState, runtime: Runtime[TutorContext]) -> dict[str, Any]:
        """Choose the path. This is where two learners diverge on one mission."""
        mission = self._mission(state)
        scores = dict(state.get("mastery") or {})

        chosen: list[str] = []
        skipped: list[str] = []
        for step in mission.steps:
            threshold = step.skip_if_mastered
            if threshold > 0 and step.concepts:
                floor = min(
                    scores.get(c, mastery_model.DEFAULT_PRIOR) for c in step.concepts
                )
                if floor >= threshold:
                    skipped.append(step.id)
                    continue
            chosen.append(step.id)

        if not chosen:  # never leave a learner with nothing to do
            chosen = [mission.steps[-1].id] if mission.steps else []
            skipped = [s for s in skipped if s not in chosen]

        emit(runtime, "plan.ready", steps=chosen, skipped=skipped)
        return {
            "phase": "investigate",
            "plan": chosen,
            "step_index": 0,
            "transcript": [{"role": "system", "kind": "plan", "steps": chosen, "skipped": skipped}],
        }

    async def investigate(
        self, state: TutorState, runtime: Runtime[TutorContext]
    ) -> dict[str, Any]:
        """Run the current step's declared tools. The kernel stays domain-blind."""
        mission = self._mission(state)
        step = self._current_step(state)
        if step is None:
            return {"phase": "verify"}

        ledger = Ledger(list(state.get("evidence") or []))
        outputs: dict[str, Any] = {}
        failures: list[str] = []

        for call in step.tools:
            args = dict(call.args)
            artifact_id = args.pop("artifact", None)
            if artifact_id is not None:
                artifact = mission.artifacts.get(str(artifact_id))
                if artifact is None:
                    failures.append(f"{call.call}: 未声明的工件 {artifact_id}")
                    continue
                args["path"] = str(artifact.path)

            emit(runtime, "tool.started", tool=call.call, step=step.id)
            result = self.registry.call(call.call, **args)
            key = call.as_ or call.call.rsplit(".", 1)[-1]

            if not result.ok:
                failures.append(f"{call.call}: {result.error}")
                emit(runtime, "tool.completed", tool=call.call, ok=False, error=result.error)
                continue

            outputs[key] = result.value
            item = ledger.add(
                kind="tool_result",
                source=call.call,
                summary=call.summary or f"{call.call} 的计算结果",
                locator={"step": step.id, "as": key},
                value=result.value,
            )
            emit(
                runtime,
                "tool.completed",
                tool=call.call,
                ok=True,
                duration_ms=result.duration_ms,
                evidence_id=item.id,
            )

        for query in step.knowledge:
            result = self.registry.call("kb.search", query=query, limit=2)
            if not result.ok or not result.value:
                continue
            for hit in result.value:
                ledger.add(
                    kind="knowledge",
                    source=hit.get("source", "kb"),
                    summary=hit.get("title", query),
                    locator={"section": hit.get("section", ""), "query": query},
                    value=hit.get("text", ""),
                )

        stage = StageDirective(
            scene=step.scene,  # type: ignore[arg-type]
            props={**step.stage_props, "step": step.id, **outputs},
            focus=[e["id"] for e in ledger.delta()][:3],
        )
        delta = ledger.delta()
        for entry in delta:
            emit(runtime, "evidence.added", evidence=entry)
        emit(runtime, "stage.changed", stage=stage.to_dict(), phase="coach")

        return {
            "phase": "coach",
            "current_step": step.to_dict(),
            "tool_outputs": outputs,
            "evidence": delta,
            "stage": stage.to_dict(),
            "attempts": 0,
            "hint_level": 0,
            "answer_unlocked": False,
            "last_judgement": {},
            "last_answer": {},
            "error": {"tools": failures} if failures else {},
        }

    async def coach(self, state: TutorState, runtime: Runtime[TutorContext]) -> dict[str, Any]:
        """Produce one coaching turn, then post-validate it against leaking."""
        step_dict = dict(state.get("current_step") or {})
        step = self._current_step(state)
        if step is None:
            return {"phase": "verify"}

        evidence = Ledger(list(state.get("evidence") or [])).entries
        judgement_dict = dict(state.get("last_judgement") or {})
        judgement = (
            Judgement(
                correct=bool(judgement_dict.get("correct")),
                score=float(judgement_dict.get("score", 0.0)),
                concept_scores=dict(judgement_dict.get("concept_scores", {})),
                misconceptions=list(judgement_dict.get("misconceptions", [])),
                evidence_ids=list(judgement_dict.get("evidence_ids", [])),
                feedback=str(judgement_dict.get("feedback", "")),
                detail=dict(judgement_dict.get("detail", {})),
            )
            if judgement_dict
            else None
        )

        ctx = CoachContext(
            mission_title=str(state.get("mission_title", "")),
            step_id=step.id,
            step_title=step.title,
            objective=step.objective,
            concepts=list(step.concepts),
            hint_level=int(state.get("hint_level", 0)),
            answer_unlocked=bool(state.get("answer_unlocked")),
            attempts=int(state.get("attempts", 0)),
            ask=step.ask,
            hint_ladder=list(step.hint_ladder),
            walkthrough=step.walkthrough,
            misconception_notes=self.pack.misconception_notes(
                list(state.get("misconceptions") or [])
                + (judgement.misconceptions if judgement else [])
            ),
            evidence=evidence,
            mastery=dict(state.get("mastery") or {}),
            misconceptions=list(state.get("misconceptions") or []),
            last_answer=dict(state.get("last_answer") or {}) or None,
            last_judgement=judgement,
            expects=step.expects,
            choices=list(step.choices),
        )

        try:
            move = await self.brain.next_move(ctx)
        except Exception:  # noqa: BLE001 - a provider outage must not end the lesson
            logger.exception("brain failed; falling back to the authored hint ladder")
            move = TutorMove(
                intent="hint",
                say=fallback_hint(step_dict, ctx.hint_level),
                hint_level=ctx.hint_level,
                expects=step.expects,
                choices=list(step.choices),
            )

        move, guarded = self._guard(move, step_dict, ctx)

        # Citations must resolve; a coach may not point at evidence that isn't there.
        missing = verify_citations(list(state.get("evidence") or []), move.evidence_ids)
        if missing:
            move = TutorMove(
                intent=move.intent,
                say=move.say,
                hint_level=move.hint_level,
                evidence_ids=[i for i in move.evidence_ids if i not in missing],
                expects=move.expects,
                choices=move.choices,
                rationale=move.rationale,
            )
            logger.warning("dropped unresolvable citations: %s", missing)

        emit(runtime, "coach.move", move=move.to_dict(), guarded=guarded)
        return {
            "move": move.to_dict(),
            "phase": "await_learner",
            "transcript": [{"role": "coach", **move.to_dict()}],
        }

    def _guard(
        self, move: TutorMove, step_dict: dict[str, Any], ctx: CoachContext
    ) -> tuple[TutorMove, bool]:
        """Reject a move that gives the answer away below the unlocked level.

        This is the mechanism behind "不直接代做": the check runs on the
        rendered text every single turn, so it holds regardless of which brain
        produced it or how the prompt was worded.
        """
        if move.intent == "reveal" and ctx.answer_unlocked:
            return move, False
        guard = LeakGuard.from_step(step_dict)
        verdict = check_leakage(move.say, guard, answer_unlocked=ctx.answer_unlocked)
        if not verdict.leaked:
            return move, False
        logger.info("leak guard tripped on step %s: %s", ctx.step_id, verdict.reasons)
        return (
            TutorMove(
                intent="hint",
                say=fallback_hint(step_dict, ctx.hint_level),
                hint_level=ctx.hint_level,
                evidence_ids=list(move.evidence_ids),
                expects=ctx.expects,
                choices=list(ctx.choices),
                rationale="生成的回复触发了防泄题守卫，已替换为课程包提示。",
            ),
            True,
        )

    async def await_learner(self, state: TutorState, _runtime: Runtime[TutorContext]) -> dict:
        """Pause as durable thread state, not as a blocking in-request wait."""
        move = dict(state.get("move") or {})
        answer = interrupt(
            {
                "kind": "answer",
                "step_id": str((state.get("current_step") or {}).get("id", "")),
                "prompt": move,
                "stage": dict(state.get("stage") or {}),
                "hint_level": int(state.get("hint_level", 0)),
                "attempts": int(state.get("attempts", 0)),
            }
        )
        # --- only after resume ---------------------------------------------
        payload = answer if isinstance(answer, dict) else {"text": str(answer)}
        return {
            "last_answer": payload,
            "phase": "judge",
            "transcript": [{"role": "learner", **payload}],
        }

    async def judge(self, state: TutorState, runtime: Runtime[TutorContext]) -> dict[str, Any]:
        step = self._current_step(state)
        if step is None:
            return {"phase": "verify"}

        answer = dict(state.get("last_answer") or {})
        spec = {**step.grader, "concepts": step.concepts}
        ledger = Ledger(list(state.get("evidence") or []))
        tools_ctx = dict(state.get("tool_outputs") or {})

        # A grader may need a tool run over the learner's *answer* — that is how
        # the simulator mission is graded: the client drives the console for
        # responsiveness, but the score comes from replaying the submitted
        # action log server-side, so a client cannot award itself goodput.
        score_tool = step.grader.get("score_tool")
        if isinstance(score_tool, dict) and score_tool.get("call"):
            args = dict(score_tool.get("args") or {})
            for tool_arg, answer_key in (score_tool.get("from_answer") or {}).items():
                args[str(tool_arg)] = answer.get(str(answer_key))
            emit(runtime, "tool.started", tool=score_tool["call"], step=step.id)
            result = self.registry.call(str(score_tool["call"]), **args)
            key = str(step.grader.get("score_from", "score"))
            if result.ok:
                tools_ctx[key] = result.value
                item = ledger.add(
                    kind="simulation_frame",
                    source=str(score_tool["call"]),
                    summary="按你的操作序列重跑仿真得到的结果",
                    locator={"step": step.id, "as": key},
                    value=result.value,
                )
                emit(
                    runtime,
                    "tool.completed",
                    tool=score_tool["call"],
                    ok=True,
                    duration_ms=result.duration_ms,
                    evidence_id=item.id,
                )
            else:
                emit(
                    runtime,
                    "tool.completed",
                    tool=score_tool["call"],
                    ok=False,
                    error=result.error,
                )

        judgement = grade(spec, answer, {"tools": tools_ctx})

        record = ledger.add(
            kind="learner_action",
            source=f"answer.{step.id}",
            summary=f"作答 {step.id}：{'通过' if judgement.correct else '未通过'}",
            locator={"step": step.id, "attempt": int(state.get("attempts", 0)) + 1},
            value={"answer": answer, "judgement": judgement.to_dict()},
        )
        judged = Judgement(
            correct=judgement.correct,
            score=judgement.score,
            concept_scores=judgement.concept_scores,
            misconceptions=judgement.misconceptions,
            evidence_ids=[*judgement.evidence_ids, record.id],
            feedback=judgement.feedback,
            detail=judgement.detail,
        )
        emit(runtime, "answer.judged", judgement=judged.to_dict(), step=step.id)
        return {
            "last_judgement": judged.to_dict(),
            "attempts": int(state.get("attempts", 0)) + 1,
            "misconceptions": list(judged.misconceptions),
            "evidence": ledger.delta(),
            "phase": "advance",
        }

    async def advance(self, state: TutorState, runtime: Runtime[TutorContext]) -> dict[str, Any]:
        """Fold the result into the learner model and decide what happens next."""
        step = self._current_step(state)
        judgement = dict(state.get("last_judgement") or {})
        correct = bool(judgement.get("correct"))
        attempts = int(state.get("attempts", 0))
        hint_level = int(state.get("hint_level", 0))
        answer = dict(state.get("last_answer") or {})

        counts = {k: float(v) for k, v in (state.get("mastery_counts") or {}).items()}
        updated, changes = mastery_model.apply(
            dict(state.get("mastery") or {}),
            dict(judgement.get("concept_scores") or {}),
            hint_level=hint_level,
            evidence_ids=list(judgement.get("evidence_ids") or []),
            counts={k: int(v) for k, v in counts.items()},
            reason=f"步骤 {step.id if step else '?'} 第 {attempts} 次作答",
        )
        for concept in (judgement.get("concept_scores") or {}):
            counts[concept] = float(counts.get(concept, 0.0)) + 1.0

        exhausted = step is not None and attempts >= step.max_attempts
        unlocked = bool(state.get("answer_unlocked")) or should_unlock_answer(
            attempts=attempts,
            step=step.to_dict() if step else {},
            learner_requested=bool(answer.get("request_walkthrough")),
        )
        finished = correct or exhausted or unlocked

        update: dict[str, Any] = {
            "mastery": updated,
            "mastery_counts": counts,
            "mastery_changes": [c.to_dict() for c in changes],
            "answer_unlocked": unlocked,
        }
        if changes:
            emit(runtime, "mastery.updated", changes=[c.to_dict() for c in changes])

        if finished:
            update["step_results"] = [
                {
                    "step_id": step.id if step else "",
                    "concepts": list(step.concepts) if step else [],
                    "attempts": attempts,
                    "hint_level": hint_level,
                    "correct": correct,
                    "resolved": "correct" if correct else ("revealed" if unlocked else "exhausted"),
                    "misconceptions": list(judgement.get("misconceptions") or []),
                    "evidence_ids": list(judgement.get("evidence_ids") or []),
                }
            ]
            update["step_index"] = int(state.get("step_index", 0)) + 1
            update["phase"] = "investigate"
            emit(
                runtime,
                "step.completed",
                step=step.id if step else "",
                correct=correct,
                attempts=attempts,
            )
            if unlocked and not correct:
                # Give the walkthrough before moving on.
                update["phase"] = "coach"
                update["step_index"] = int(state.get("step_index", 0))
            return update

        escalated = next_hint_level(attempts=attempts, current=hint_level)
        update["hint_level"] = escalated
        update["phase"] = "coach"
        if escalated != hint_level:
            emit(runtime, "hint.escalated", level=escalated, step=step.id if step else "")
        return update

    async def verify(self, state: TutorState, runtime: Runtime[TutorContext]) -> dict[str, Any]:
        mission = self._mission(state)
        answers = interrupt(
            {
                "kind": "verify",
                "title": "最后两题，检验一下是不是真的掌握了",
                "items": [public_item(i) for i in mission.verify],
                "stage": StageDirective(scene="verify", props={"mission": mission.id}).to_dict(),
            }
        )
        # --- only after resume ---------------------------------------------
        answers = answers if isinstance(answers, dict) else {}
        records, overall, concept_scores, tags = self._grade_items(mission.verify, answers)

        ledger = Ledger(list(state.get("evidence") or []))
        for record in records:
            ledger.add(
                kind="learner_action",
                source=f"verify.{record['item_id']}",
                summary=f"后测 {record['item_id']}：{'对' if record['correct'] else '错'}",
                locator={"item": record["item_id"], "concept": record["concept"]},
                value={"answer": record["answer"], "score": record["score"]},
            )
        delta = ledger.delta()
        counts = {k: int(v) for k, v in (state.get("mastery_counts") or {}).items()}
        updated, changes = mastery_model.apply(
            dict(state.get("mastery") or {}),
            concept_scores,
            hint_level=0,
            evidence_ids=[e["id"] for e in delta],
            counts=counts,
            reason="后测结果",
        )
        emit(runtime, "verify.graded", score=overall, concepts=concept_scores)
        emit(runtime, "mastery.updated", changes=[c.to_dict() for c in changes])

        return {
            "phase": "report",
            "verify_results": records,
            "verify_score": round(overall, 4),
            "mastery": updated,
            "mastery_changes": [c.to_dict() for c in changes],
            "misconceptions": tags,
            "evidence": delta,
        }

    async def report(self, state: TutorState, runtime: Runtime[TutorContext]) -> dict[str, Any]:
        mission = self._mission(state)
        evidence = list(state.get("evidence") or [])
        ledger = Ledger(evidence)

        ctx = ReportContext(
            mission_title=str(state.get("mission_title", mission.title)),
            concepts=list(mission.concepts),
            mastery_before=dict(state.get("mastery_before") or {}),
            mastery_after=dict(state.get("mastery") or {}),
            misconceptions=list(state.get("misconceptions") or []),
            evidence=ledger.entries,
            step_results=list(state.get("step_results") or []),
            probe_score=float(state.get("probe_score", 0.0)),
            verify_score=float(state.get("verify_score", 0.0)),
        )
        try:
            narrative = await self.brain.narrate_report(ctx)
        except Exception:  # noqa: BLE001
            logger.exception("report narration failed; using the deterministic brain")
            from ..brains.scripted import ScriptedBrain

            narrative = await ScriptedBrain().narrate_report(ctx)

        # Strip any claim whose citations do not resolve, rather than shipping
        # a report that points at evidence which does not exist.
        citations = {
            claim: ids
            for claim, ids in narrative.citations.items()
            if not verify_citations(evidence, ids)
        }
        report = {
            **narrative.to_dict(),
            "citations": citations,
            "mission": mission.id,
            "mission_title": ctx.mission_title,
            "probe_score": ctx.probe_score,
            "verify_score": ctx.verify_score,
            "learning_gain": round(ctx.verify_score - ctx.probe_score, 4),
            "mastery_before": ctx.mastery_before,
            "mastery_after": ctx.mastery_after,
            "mastery_gain": mastery_model.gain(ctx.mastery_before, ctx.mastery_after),
            "misconceptions": ctx.misconceptions,
            "step_results": ctx.step_results,
            "evidence_count": len(evidence),
        }
        emit(runtime, "report.ready", report=report)
        return {"phase": "done", "report": report}


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------


def route_after_investigate(state: TutorState) -> str:
    return "verify" if str(state.get("phase")) == "verify" else "coach"


def route_after_advance(state: TutorState) -> str:
    """retry the same step · move to the next one · or go to the post-test."""
    phase = str(state.get("phase"))
    if phase == "coach":
        return "coach"
    plan = list(state.get("plan") or [])
    return "investigate" if int(state.get("step_index", 0)) < len(plan) else "verify"


def build_graph(
    *,
    pack: Pack,
    brain: TutorBrain,
    registry: ToolRegistry,
    checkpointer: Any | None = None,
    store: Any | None = None,
) -> Any:
    kernel = TutoringKernel(pack=pack, brain=brain, registry=registry)

    builder = StateGraph(
        TutorState,
        context_schema=TutorContext,
        name="lingxilearn-tutoring-kernel",
        version="1.0.0",
    )
    builder.add_node("intake", kernel.intake)
    builder.add_node("diagnose", kernel.diagnose)
    builder.add_node("plan", kernel.plan)
    builder.add_node("investigate", kernel.investigate)
    builder.add_node("coach", kernel.coach, timeout=90)
    builder.add_node("await_learner", kernel.await_learner)
    builder.add_node("judge", kernel.judge)
    builder.add_node("advance", kernel.advance)
    builder.add_node("verify", kernel.verify)
    builder.add_node("report", kernel.report, timeout=90)

    builder.add_edge(START, "intake")
    builder.add_edge("intake", "diagnose")
    builder.add_edge("diagnose", "plan")
    builder.add_edge("plan", "investigate")
    builder.add_conditional_edges(
        "investigate", route_after_investigate, {"coach": "coach", "verify": "verify"}
    )
    builder.add_edge("coach", "await_learner")
    builder.add_edge("await_learner", "judge")
    builder.add_edge("judge", "advance")
    builder.add_conditional_edges(
        "advance",
        route_after_advance,
        {"coach": "coach", "investigate": "investigate", "verify": "verify"},
    )
    builder.add_edge("verify", "report")
    builder.add_edge("report", END)

    compile_options: dict[str, Any] = {"checkpointer": checkpointer}
    if store is not None:
        compile_options["store"] = store
    return builder.compile(**compile_options)
