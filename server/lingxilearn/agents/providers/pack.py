"""Course-pack capabilities, lifted out of the tutoring kernel's fixed pipeline.

``kernel/graph.py`` wired these as a chain: intake → diagnose → plan →
investigate → coach → await_learner → judge → advance → verify → report.  The
chain is gone; the work is not.  Each node's *content* became a capability the
orchestrator can schedule when the state calls for it, and the parts that were
already deterministic — graders, the hint ladder, the evidence ledger, mastery —
are reused unchanged rather than reimplemented.

What disappeared is the sequencing: probing before teaching is now a ranking
outcome, not an edge.
"""

from __future__ import annotations

import logging
from typing import Any

from ...kernel.evidence import Ledger
from ...kernel.graders import grade
from ...state.evidence import EvidenceRecord, Signal
from ..model_runtime import emit
from .base import ProviderContext, ProviderError, ProviderResult, register

logger = logging.getLogger(__name__)


def _mission(context: ProviderContext) -> Any:
    """The pack mission this task is working through, if there is one."""

    pack = context.pack
    mission_id = str(context.task.inputs.get("mission_id") or "")
    if pack is None or not mission_id:
        return None
    return pack.missions.get(mission_id)


def _public_item(item: Any) -> dict[str, Any]:
    """The learner-facing shape of a question — never includes the answer key."""

    return {
        "id": item.id,
        "concept": item.concept,
        "prompt": item.prompt,
        "expects": item.expects,
        "choices": list(item.choices),
        "difficulty": item.difficulty,
    }


@register(
    "pack_probe",
    display_name="实验探查",
    description="检查实验环境状态",
    execution_kind="deterministic",
)
async def pack_probe(context: ProviderContext) -> ProviderResult:
    """Serve or grade a course-pack probe (``assess.generate``/``assess.grade``).

    One provider for both halves because a probe is a single interaction: the
    orchestrator schedules it, the learner answers, and the answers are graded
    against the pack's declared graders on the way back in.
    """

    mission = _mission(context)
    if mission is None:
        raise ProviderError("pack_probe requires a pack mission")

    phase = str(context.task.inputs.get("phase") or "probe")
    items = list(mission.verify if phase == "verify" else mission.probe)
    if not items:
        raise ProviderError(f"mission {mission.id} declares no {phase} items")

    answers = dict(context.task.inputs.get("answers") or {})
    if not answers:
        # Nothing submitted yet: hand the questions out and wait.
        return ProviderResult(
            status="incomplete",
            learner_message=f"先花一分钟看看这 {len(items)} 道题。",
            data={"phase": phase, "items": [_public_item(item) for item in items]},
            persist_as=f"pack_{phase}",
            detail=f"已发出 {len(items)} 道{phase}题，等待作答",
        )

    ledger = Ledger()
    evidence: list[EvidenceRecord] = []
    records: list[dict[str, Any]] = []
    hint_level = int(context.task.inputs.get("hint_level") or 0)

    for item in items:
        spec = {**item.grader, "concepts": [item.concept]}
        judgement = grade(spec, answers.get(item.id))
        ledger.add(
            kind="learner_action",
            source=f"{phase}.{item.id}",
            summary=f"{phase} {item.id}：{'对' if judgement.correct else '错'}",
            locator={"item": item.id, "concept": item.concept},
            value={"answer": answers.get(item.id), "score": judgement.score},
        )
        records.append({"item_id": item.id, "concept": item.concept, **judgement.to_dict()})

        answered = answers.get(item.id) not in (None, "", [], {})
        evidence.append(
            EvidenceRecord(
                learner_id=context.learner_id,
                knowledge_point=item.concept,
                signal=(
                    Signal.NO_ANSWER
                    if not answered
                    else (Signal.CORRECT if judgement.correct else Signal.INCORRECT)
                ),
                source_agent="pack_probe",
                score=round(judgement.score, 4),
                misconceptions=tuple(judgement.misconceptions),
                hint_level=hint_level,
                task_id=context.task_id,
                summary=f"{phase} {item.id}",
                locator={"item": item.id, "mission": mission.id},
            )
        )

    overall = round(sum(r["score"] for r in records) / len(records), 4) if records else 0.0
    emit(context.runtime, "assessment.graded", agent="pack_probe", overall=overall)
    return ProviderResult(
        learner_message=f"{phase} 判分完成，总体 {overall:.0%}。",
        evidence=evidence,
        data={"phase": phase, "records": records, "overall": overall, "ledger": ledger.delta()},
        persist_as=f"pack_{phase}",
        detail=f"{phase} 判分 {len(records)} 题，总体 {overall:.2f}",
    )


@register(
    "pack_investigate",
    display_name="实验排查",
    description="排查实验环境问题",
    execution_kind="deterministic",
)
async def pack_investigate(context: ProviderContext) -> ProviderResult:
    """Run the step's declared tools over real artifacts (``tool.investigate``).

    The registry resolves capability names to real Python, so adding a subject
    means registering a namespace — never editing this provider.
    """

    if context.registry is None:
        raise ProviderError("pack_investigate requires the tool registry")

    calls = list(context.task.inputs.get("tools") or [])
    if not calls:
        raise ProviderError("pack_investigate was scheduled with no tool calls")

    ledger = Ledger()
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for call in calls:
        name = str(call.get("name") or "")
        arguments = dict(call.get("args") or {})
        outcome = context.registry.call(name, **arguments)
        entry = ledger.add(
            kind="tool_result",
            source=name,
            summary=f"{name} → {'ok' if outcome.ok else outcome.error}",
            locator={"tool": name},
            value=outcome.value if outcome.ok else None,
        )
        record = {
            "tool": name,
            "args": arguments,
            "ok": outcome.ok,
            "duration_ms": outcome.duration_ms,
            "evidence_id": entry.id,
            "error": outcome.error,
        }
        results.append(record)
        if not outcome.ok:
            failures.append(record)

    evidence = [
        EvidenceRecord(
            learner_id=context.learner_id,
            knowledge_point=context.knowledge_point_id,
            signal=Signal.ERROR_PATTERN,
            source_agent="pack_investigate",
            task_id=context.task_id,
            summary=f"工具 {item['tool']} 执行失败：{item['error']}",
            payload={"tool": item["tool"]},
        )
        for item in failures
    ]
    return ProviderResult(
        # A tool failure is teaching material, not a 500.
        status="completed" if not failures else "incomplete",
        evidence=evidence,
        data={"calls": results, "ledger": ledger.delta()},
        persist_as="investigation",
        detail=f"执行 {len(results)} 个工具，{len(failures)} 个失败",
        warnings=[f"{item['tool']}：{item['error']}" for item in failures],
    )


@register(
    "pack_report",
    display_name="实验报告",
    description="汇总实验结果",
    execution_kind="deterministic",
)
async def pack_report(context: ProviderContext) -> ProviderResult:
    """Summarise the goal from the profile diff and the ledger (``meta.report``).

    Built from recorded before/after values rather than from the conversation,
    so a claim in the report is always backed by a row someone can open.
    """

    changes = list(context.task.inputs.get("profile_changes") or [])
    mastery_changes = [
        {
            "knowledge_point_id": item.get("knowledge_point_id"),
            "before": (item.get("before") or {}).get("mastery"),
            "after": (item.get("after") or {}).get("mastery"),
            "evidence_ids": item.get("evidence_ids") or [],
        }
        for item in changes
    ]
    improved = [
        item
        for item in mastery_changes
        if item["before"] is not None
        and item["after"] is not None
        and item["after"] > item["before"]
    ]
    unverified = [
        row.get("knowledge_point_id")
        for row in context.profile.values()
        if int((row.get("system") or {}).get("evidence_count") or 0) < 2
    ]
    open_misconceptions = sorted(
        {
            tag
            for row in context.profile.values()
            for tag in ((row.get("system") or {}).get("misconceptions") or [])
        }
    )

    if improved:
        headline = "、".join(
            f"{item['knowledge_point_id']}（{item['before']:.2f}→{item['after']:.2f}）"
            for item in improved[:3]
        )
        summary = f"这次掌握度有提升的是：{headline}。"
    else:
        summary = "这次还没有形成明确的掌握度提升，证据仍然偏少。"
    if open_misconceptions:
        summary += f" 仍有待消解的误区：{'、'.join(open_misconceptions[:2])}。"

    return ProviderResult(
        learner_message=summary,
        data={
            "goal_id": context.goal.id,
            "summary": summary,
            "mastery_changes": mastery_changes,
            "open_misconceptions": open_misconceptions,
            "unverified": [item for item in unverified if item],
        },
        persist_as="report",
        detail=f"报告覆盖 {len(mastery_changes)} 个知识点",
    )


__all__ = ["pack_investigate", "pack_probe", "pack_report"]
