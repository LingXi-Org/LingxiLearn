"""Curriculum graph builder sidecar integration."""

from __future__ import annotations

import json
from typing import Any

from lingxigraph import FilesystemSkillSource, HumanMessage, SkillRegistry, create_agent

from ..config import REPO_ROOT
from ..store.knowledge_graph import validate_result
from .contracts import extract_json
from .graph import _agent_model, _invoke_agent, _message_text
from .skill_runtime import progressive_skill_prompt, skill_constraints

GRAPH_PROMPT = progressive_skill_prompt(
    "curriculum-graph-builder",
    "curriculum-graph-builder-result.v1",
    referenced_resources=(
        "references/curriculum-graph-builder-task.schema.json",
        "references/curriculum-graph-builder-result.schema.json",
        "references/graph-model.md",
        "references/merge-policy.md",
        "references/quality-gate.md",
        "references/system-integration-contract.md",
    ),
    artifact_instructions="""这是后台课程知识图谱 proposal Agent。只返回 curriculum-graph-builder-result.v1 JSON，
不要返回 Markdown，不要写数据库，不要输出 learner-facing 教学回复。严格遵循来源边界、稳定 ID、
增量 patch、revision 和 learner overlay 约束；没有可靠关系时返回 create_graph 或 no_change，并写出中文 warning。""",
)


async def build_curriculum_graph_proposal(
    *,
    model: Any,
    task: dict[str, Any],
    existing_graphs: list[dict[str, Any]],
    runtime: Any,
) -> dict[str, Any]:
    """Ask the upstream graph Skill for a validated, host-facing patch."""

    intent = task.get("intent") or {}
    messages = task.get("user_messages") or []
    source_materials: list[dict[str, Any]] = [
        {
            "source_id": f"{task['id']}:prompt",
            "kind": "user_message",
            "content": task.get("prompt", ""),
        }
    ]
    for index, message in enumerate(messages[-20:]):
        source_materials.append(
            {
                "source_id": f"{task['id']}:message:{index}",
                "kind": "user_message",
                "content": message.get("message", message) if isinstance(message, dict) else message,
            }
        )
    if task.get("lecture_result"):
        source_materials.append(
            {
                "source_id": f"{task['id']}:lesson-intro",
                "kind": "lesson_intro",
                "content": {key: value for key, value in task["lecture_result"].items() if key != "html"},
            }
        )
    if task.get("deck_result"):
        source_materials.append(
            {
                "source_id": f"{task['id']}:lecture-deck",
                "kind": "lecture_deck",
                "content": task["deck_result"],
            }
        )
    if task.get("quiz_result"):
        source_materials.append(
            {
                "source_id": f"{task['id']}:quiz",
                "kind": "quiz",
                "content": task["quiz_result"],
            }
        )
    if task.get("quiz_submission"):
        source_materials.append(
            {
                "source_id": f"{task['id']}:quiz-submission",
                "kind": "assessment_evidence",
                "content": task["quiz_submission"],
            }
        )
    request = {
        "schema_version": "curriculum-graph-builder-task.v1",
        "task_id": task["id"],
        "learning_context": {
            "topic": intent.get("topic") or task.get("prompt", "知识主题"),
            "learning_objective": intent.get("learning_objective", ""),
            "course_context": intent.get("course_context", ""),
            "source_materials": source_materials,
        },
        "graph_policy": {"mode": "auto", "max_new_nodes": 12, "allow_position_hints": False},
        "existing_graphs": existing_graphs,
    }
    registry = SkillRegistry(
        (FilesystemSkillSource(REPO_ROOT / "skills" / "curriculum-graph-builder"),)
    )
    agent = create_agent(
        _agent_model(model, "curriculum_graph_builder"),
        skills=registry,
        system_prompt=GRAPH_PROMPT,
        pinned_constraints=skill_constraints(
            "curriculum-graph-builder",
            (
                "references/curriculum-graph-builder-task.schema.json",
                "references/curriculum-graph-builder-result.schema.json",
                "references/graph-model.md",
                "references/merge-policy.md",
                "references/quality-gate.md",
                "references/system-integration-contract.md",
            ),
            stage_artifacts=False,
        ),
        name="curriculum-graph-builder",
    )
    result = await _invoke_agent(
        agent,
        HumanMessage(json.dumps(request, ensure_ascii=False)),
        runtime,
        agent_name="curriculum_graph_builder",
        recursion_limit=16,
    )
    parsed = extract_json(_message_text(result))
    if not parsed:
        raise ValueError("curriculum-graph-builder returned no JSON result")
    existing = None
    target = (parsed.get("decision") or {}).get("target_graph_id")
    if target:
        existing = next((graph for graph in existing_graphs if graph.get("graph_id") == target), None)
    validate_result(parsed, existing)
    return parsed
