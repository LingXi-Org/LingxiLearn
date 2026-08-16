"""Providers that act on the capability system itself.

Both are deliberately off the learner's critical path: one drafts a new skill
when the registry cannot serve a goal, the other evaluates skills during
development.  Neither may change what runs without a human saying so.
"""

from __future__ import annotations

import json
import logging

from lingxigraph import FilesystemSkillSource, HumanMessage, SkillRegistry, create_agent

from ...config import REPO_ROOT
from ...state.capabilities import all_tags
from ...state.skill_catalog import SkillManifestError, parse_manifest
from ..contracts import extract_json
from ..model_runtime import agent_model, emit, invoke_agent, message_text
from .base import ProviderContext, ProviderError, ProviderResult, register

logger = logging.getLogger(__name__)

FORGE_PROMPT = """你是能力起草 Agent。编排器报告了一个能力缺口。

先自问三件事：真的缺能力，还是候选只是被前置条件挡住了？现有 skill 换一组输入能不能覆盖？
这个缺口会重复出现吗？任一指向「不需要」就返回 {"action":"no_forge","reason":"..."}。

要起草时，metadata.capabilities 只能从给定的能力词表里选。词表里没有合适的标签说明这是
架构变更而不是新技能，同样返回 no_forge。

只输出 JSON：
{"action":"forge","skill_id":"kebab-case","manifest":"完整 SKILL.md 文本",
 "capability_gap":"...","reason":"..."}"""


@register(
    "skill_forge",
    display_name="技能锻造",
    description="为学习者定制新技能",
    execution_kind="model",
)
async def skill_forge(context: ProviderContext) -> ProviderResult:
    """Draft a skill for an unserved capability (``meta.author_skill``).

    Returns the draft; it does not install it.  Registration happens in dispatch
    and always lands disabled, because enabling a new capability changes what
    the runtime may do to a learner and that is the learner's call.
    """

    gap = str(context.task.inputs.get("capability_gap") or "").strip()
    if not gap:
        raise ProviderError("skill_forge was scheduled without a capability gap")
    if context.model is None:
        raise ProviderError("skill-forge requires a model")

    emit(context.runtime, "agent.started", agent="skill_forge", skill="skill-forge")
    payload = {
        "capability_gap": gap,
        "goal": context.goal.to_dict(),
        "available_capabilities": list(all_tags()),
        "existing_skills": list(context.task.inputs.get("existing_skills") or [])[:40],
    }
    agent = create_agent(
        agent_model(context.model, "skill_forge"),
        skills=SkillRegistry((FilesystemSkillSource(REPO_ROOT / "skills" / "skill-forge"),)),
        system_prompt=FORGE_PROMPT,
        name="skill-forge",
    )
    parsed = (
        extract_json(
            message_text(
                await invoke_agent(
                    agent,
                    HumanMessage(json.dumps(payload, ensure_ascii=False)),
                    context.runtime,
                    agent_name="skill_forge",
                    recursion_limit=10,
                )
            )
        )
        or {}
    )

    if str(parsed.get("action") or "no_forge") != "forge":
        return ProviderResult(
            data={"action": "no_forge", "reason": str(parsed.get("reason") or "无需新增能力")},
            persist_as="skill_forge",
            detail=str(parsed.get("reason") or "判定无需起草新技能"),
        )

    skill_id = str(parsed.get("skill_id") or "").strip()
    manifest_text = str(parsed.get("manifest") or "")
    if not skill_id or not manifest_text:
        raise ProviderError("skill-forge returned no usable manifest")

    try:
        manifest = parse_manifest(manifest_text, skill_id=skill_id, source="forged")
    except SkillManifestError as exc:
        raise ProviderError(f"forged manifest is unreadable: {exc}") from exc
    if not manifest.capabilities:
        raise ProviderError("a forged skill with no capability could never be selected")

    return ProviderResult(
        learner_message=(
            f"我发现现有能力覆盖不了「{gap}」，起草了一个新技能 {skill_id}。"
            "它默认是关闭的，你确认之后我才会用它。"
        ),
        data={
            "action": "forge",
            "skill_id": skill_id,
            "manifest": manifest_text,
            "capabilities": [str(c) for c in manifest.capabilities],
            "capability_gap": gap,
            "reason": str(parsed.get("reason") or ""),
            "enabled": False,
            "requires_confirmation": True,
        },
        persist_as="skill_forge",
        detail=f"起草技能 {skill_id}（默认禁用）",
    )


@register(
    "skill_eval",
    display_name="技能评估",
    description="评估技能质量",
    execution_kind="model",
)
async def skill_eval(context: ProviderContext) -> ProviderResult:
    """Evaluate a skill against the harness (``meta.evaluate``).

    A development capability.  ``candidates`` excludes it from the learner's
    runtime path, so it only runs when something schedules it explicitly.
    """

    target = str(context.task.inputs.get("skill_id") or "").strip()
    if not target:
        raise ProviderError("skill_eval was scheduled without a target skill")

    harness = REPO_ROOT / "skills" / "skill-eval-harness"
    if not harness.is_dir():
        raise ProviderError("the skill-eval-harness skill is not installed")

    return ProviderResult(
        data={
            "skill_id": target,
            "harness": str(harness.relative_to(REPO_ROOT)),
            "status": "queued",
        },
        persist_as="skill_eval",
        detail=f"已排入 {target} 的技能评测",
    )


__all__ = ["skill_eval", "skill_forge"]
