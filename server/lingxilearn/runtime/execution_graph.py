"""The canonical execution graph, derived from AgentRun facts (issue #18 §14).

Nodes are AgentRuns — the same identity the left-side chat renders — so the
right-side graph can never disagree with the chat about who ran.  Edges carry
only real product semantics (work dependency, agent delegation); runtime
mechanics nodes never appear.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def build_execution_graph(
    runs: list[dict[str, Any]],
    *,
    task_id: str,
    work_dependencies: list[Mapping[str, Any]] | None = None,
    skill_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build nodes/edges/parallel groups from durable AgentRun rows.

    ``work_dependencies`` items map ``work_id``/``depends_on_id`` (the Work
    Ledger's edges) onto the runs that executed those work items, producing
    ``dependency`` edges.  ``skill_runs`` attach the skill ids each run used.
    """

    skills_by_run: dict[str, list[str]] = {}
    for skill in skill_runs or []:
        run_id = str(skill.get("agent_run_id") or "")
        if run_id:
            skills_by_run.setdefault(run_id, []).append(str(skill.get("skill_id") or ""))

    run_by_work: dict[str, list[str]] = {}
    for run in runs:
        work_id = str(run.get("work_item_id") or "")
        if work_id:
            run_by_work.setdefault(work_id, []).append(str(run.get("id") or ""))

    nodes: list[dict[str, Any]] = []
    for run in runs:
        run_id = str(run.get("id") or "")
        if not run_id:
            continue
        nodes.append(
            {
                "id": run_id,
                "turnId": str(run.get("turn_id") or ""),
                "executionId": str(run.get("execution_id") or ""),
                "parentAgentRunId": str(run.get("parent_agent_run_id") or "") or None,
                "providerId": str(run.get("provider_id") or ""),
                "displayName": str(run.get("agent_display_name") or run.get("provider_id") or ""),
                "executionKind": str(run.get("execution_kind") or "model"),
                "capability": str(run.get("capability") or ""),
                "skillIds": skills_by_run.get(run_id, []),
                "status": str(run.get("status") or "queued"),
                "startedAt": run.get("started_at"),
                "endedAt": run.get("ended_at"),
                "presentationRole": str(run.get("presentation_role") or "supporting"),
                "artifactResourceIds": [],
            }
        )

    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(source: str, target: str, kind: str) -> None:
        if not source or not target or source == target:
            return
        key = (source, target, kind)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({"source": source, "target": target, "kind": kind})

    for run in runs:
        parent = str(run.get("parent_agent_run_id") or "")
        if parent:
            add_edge(parent, str(run.get("id") or ""), "agent-delegation")

    dependency_pairs: set[tuple[str, str]] = set()
    for dep in work_dependencies or []:
        work_id = str(dep.get("work_id") or "")
        depends_on = str(dep.get("depends_on_id") or "")
        for source in run_by_work.get(depends_on, []):
            for target in run_by_work.get(work_id, []):
                dependency_pairs.add((source, target))
                add_edge(source, target, "dependency")

    # Parallel groups: same execution, same parent, overlapping time windows,
    # and no dependency edge between them (issue #18 §14.4 — parallelism is a
    # graph fact, not a layout guess).
    parallel_group_of: dict[str, str] = {}
    group_counter = 0
    by_execution: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        by_execution.setdefault(str(run.get("execution_id") or ""), []).append(run)
    for execution_runs in by_execution.values():
        for index, left in enumerate(execution_runs):
            for right in execution_runs[index + 1 :]:
                left_id = str(left.get("id") or "")
                right_id = str(right.get("id") or "")
                if not _overlaps(left, right):
                    continue
                if str(left.get("parent_agent_run_id") or "") != str(
                    right.get("parent_agent_run_id") or ""
                ):
                    continue
                if (left_id, right_id) in dependency_pairs or (
                    right_id,
                    left_id,
                ) in dependency_pairs:
                    continue
                left_group = parallel_group_of.get(left_id)
                right_group = parallel_group_of.get(right_id)
                if left_group and right_group:
                    continue
                group = left_group or right_group or f"pg_{group_counter}"
                if not left_group and not right_group:
                    group_counter += 1
                parallel_group_of[left_id] = group
                parallel_group_of[right_id] = group
    for node in nodes:
        node["parallelGroupId"] = parallel_group_of.get(node["id"]) or None

    return {
        "taskId": task_id,
        "nodes": nodes,
        "edges": edges,
    }


def _overlaps(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_start = str(left.get("started_at") or "")
    right_start = str(right.get("started_at") or "")
    if not left_start or not right_start:
        return False
    left_end = str(left.get("ended_at") or "") or "9999"
    right_end = str(right.get("ended_at") or "") or "9999"
    return left_start < right_end and right_start < left_end


def visible_agent_run_ids(graph: Mapping[str, Any]) -> set[str]:
    """The left-side chat's visible agent identities for parity assertions."""

    return {str(node.get("id") or "") for node in graph.get("nodes") or []}


__all__ = ["build_execution_graph", "visible_agent_run_ids"]
