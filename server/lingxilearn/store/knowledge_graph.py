"""Validation and normalization helpers for learner-owned curriculum graphs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:  # pragma: no cover - dependency is part of the server runtime
    jsonschema = None


RELATIONS = {
    "prerequisite_of",
    "foundation_for",
    "part_of",
    "leads_to",
    "applies_to",
    "contrasts_with",
    "commonly_confused_with",
    "related_to",
}
LEARNING_STATES = {
    "unknown",
    "not_observed",
    "emerging",
    "demonstrated",
    "misconception_evidence",
    "needs_recheck",
}
NODE_TYPES = {
    "domain",
    "topic",
    "concept",
    "skill",
    "method",
    "formula",
    "example",
    "misconception",
    "application",
}


class GraphValidationError(ValueError):
    """The proposal did not satisfy the upstream Skill contract."""


class GraphRevisionConflict(ValueError):
    """The proposal was generated from an outdated graph revision."""


def _schema_path(name: str) -> Path:
    return Path(__file__).resolve().parents[3] / "skills" / "curriculum-graph-builder" / "references" / name


def validate_task(task: dict[str, Any]) -> None:
    _validate_schema(task, "curriculum-graph-builder-task.schema.json")


def validate_result(result: dict[str, Any], existing_graph: dict[str, Any] | None = None) -> None:
    _validate_schema(result, "curriculum-graph-builder-result.schema.json")
    if result.get("status") in {"conflict", "insufficient_context"}:
        return
    semantic_checks(result, existing_graph)


def normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    """Validate and return a JSON-safe copy for sidecar boundaries."""

    value = json.loads(json.dumps(task, ensure_ascii=False, default=str))
    validate_task(value)
    return value


def _validate_schema(value: dict[str, Any], schema_name: str) -> None:
    if jsonschema is None:
        raise GraphValidationError("jsonschema is required for curriculum graph validation")
    try:
        schema = json.loads(_schema_path(schema_name).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise GraphValidationError(f"unable to load graph schema: {schema_name}") from exc
    except jsonschema.ValidationError as exc:
        raise GraphValidationError(exc.message) from exc


def semantic_checks(result: dict[str, Any], existing_graph: dict[str, Any] | None = None) -> None:
    decision = result["decision"]
    action = decision["action"]
    patch = result["graph_patch"]
    if action == "create_graph" and (decision["target_graph_id"] is not None or decision["base_revision"] is not None):
        raise GraphValidationError("create_graph must not target an existing graph")
    if action == "create_graph" and not decision.get("proposed_title"):
        raise GraphValidationError("create_graph requires proposed_title")
    if action in {"extend_graph", "update_graph"} and (
        not decision["target_graph_id"] or decision["base_revision"] is None
    ):
        raise GraphValidationError("graph extension/update requires target_graph_id and base_revision")
    if action == "no_change" and any(patch[key] for key in patch):
        raise GraphValidationError("no_change must have an empty patch")

    added_nodes = patch["add_nodes"]
    added_edges = patch["add_edges"]
    node_ids = [node["id"] for node in added_nodes]
    edge_ids = [edge["id"] for edge in added_edges]
    if len(node_ids) != len(set(node_ids)):
        raise GraphValidationError("duplicate node id in add_nodes")
    if len(edge_ids) != len(set(edge_ids)):
        raise GraphValidationError("duplicate edge id in add_edges")

    existing_nodes = {node["id"] for node in (existing_graph or {}).get("nodes", [])}
    existing_edges = {edge["id"] for edge in (existing_graph or {}).get("edges", [])}
    if existing_nodes.intersection(node_ids):
        raise GraphValidationError("new node id collides with existing graph")
    if existing_edges.intersection(edge_ids):
        raise GraphValidationError("new edge id collides with existing graph")

    known_nodes = existing_nodes | set(node_ids)
    known_edges = existing_edges | set(edge_ids)
    semantic_edges: set[tuple[str, str, str]] = set()
    existing_edge_by_id: dict[str, dict[str, Any]] = {}
    for edge in (existing_graph or {}).get("edges", []):
        existing_edge_by_id[edge["id"]] = edge
        relation = edge["relation"]
        source, target = edge["source"], edge["target"]
        if relation in {"contrasts_with", "commonly_confused_with", "related_to"}:
            source, target = sorted((source, target))
        semantic_edges.add((source, target, relation))
    for node in added_nodes:
        if node["type"] not in NODE_TYPES or node["learning_state"] not in LEARNING_STATES:
            raise GraphValidationError(f"invalid node type or learning state: {node['id']}")
        if not 0 <= float(node["importance"]) <= 1:
            raise GraphValidationError(f"node importance out of range: {node['id']}")
    for edge in added_edges:
        if edge["source"] == edge["target"]:
            raise GraphValidationError(f"self-loop not allowed: {edge['id']}")
        if edge["source"] not in known_nodes or edge["target"] not in known_nodes:
            raise GraphValidationError(f"edge references unknown node: {edge['id']}")
        if edge["relation"] not in RELATIONS:
            raise GraphValidationError(f"unknown edge relation: {edge['relation']}")
        symmetric = edge["relation"] in {"contrasts_with", "commonly_confused_with", "related_to"}
        if symmetric and edge["directed"]:
            raise GraphValidationError(f"symmetric relation must be undirected: {edge['id']}")
        if not symmetric and not edge["directed"]:
            raise GraphValidationError(f"directional relation must be directed: {edge['id']}")
        source, target = edge["source"], edge["target"]
        if edge["relation"] in {"contrasts_with", "commonly_confused_with", "related_to"}:
            source, target = sorted((source, target))
        triple = (source, target, edge["relation"])
        if triple in semantic_edges:
            raise GraphValidationError(f"duplicate semantic edge: {triple}")
        semantic_edges.add(triple)

    for update in patch["update_nodes"]:
        if update["id"] not in known_nodes:
            raise GraphValidationError(f"update_nodes references unknown node: {update['id']}")
        if "type" in update["set"] and update["set"]["type"] not in NODE_TYPES:
            raise GraphValidationError(f"invalid updated node type: {update['id']}")
        if "importance" in update["set"] and not 0 <= float(update["set"]["importance"]) <= 1:
            raise GraphValidationError(f"updated node importance out of range: {update['id']}")
    for update in patch["update_edges"]:
        if update["id"] not in known_edges:
            raise GraphValidationError(f"update_edges references unknown edge: {update['id']}")
        values = update["set"]
        current = existing_edge_by_id.get(update["id"], {})
        relation = values.get("relation", current.get("relation"))
        directed = values.get("directed", current.get("directed"))
        if relation not in RELATIONS:
            raise GraphValidationError(f"unknown updated edge relation: {relation}")
        symmetric = relation in {"contrasts_with", "commonly_confused_with", "related_to"}
        if directed is not None and bool(directed) == symmetric:
            raise GraphValidationError(f"invalid updated edge direction: {update['id']}")
        source, target = current.get("source"), current.get("target")
        if source and target:
            old_source, old_target = source, target
            if symmetric:
                source, target = sorted((source, target))
            prospective = (source, target, relation)
            old_triple = (old_source, old_target, current.get("relation"))
            if current.get("relation") in {"contrasts_with", "commonly_confused_with", "related_to"}:
                old_triple = (*sorted((old_source, old_target)), current.get("relation"))
            if any(item == prospective for item in semantic_edges if item != old_triple):
                raise GraphValidationError(f"duplicate semantic edge after update: {update['id']}")
    for update in patch["learner_overlay_updates"]:
        if update["node_id"] not in known_nodes:
            raise GraphValidationError(f"overlay references unknown node: {update['node_id']}")


def empty_patch() -> dict[str, list[Any]]:
    return {
        "add_nodes": [],
        "update_nodes": [],
        "add_edges": [],
        "update_edges": [],
        "learner_overlay_updates": [],
    }


def graph_snapshot_dict(
    graph: Any,
    nodes: list[Any],
    edges: list[Any],
    overlays: list[Any],
) -> dict[str, Any]:
    overlay_by_node = {row.node_id: row for row in overlays}
    snapshot_nodes: list[dict[str, Any]] = []
    for row in nodes:
        overlay = overlay_by_node.get(row.node_id)
        snapshot_nodes.append(
            {
                "id": row.node_id,
                "label": row.label,
                "type": row.type,
                "importance": float(row.importance),
                "is_current": bool(overlay.is_current) if overlay else False,
                "learning_state": overlay.learning_state if overlay else "unknown",
                **({"level": row.level} if row.level is not None else {}),
                **({"position": row.position} if row.position else {}),
                **({"aliases": row.aliases} if row.aliases else {}),
                **({"description": row.description} if row.description else {}),
                **({"source_refs": row.source_refs} if row.source_refs else {}),
            }
        )
    snapshot_edges = [
        {
            "id": row.edge_id,
            "source": row.source_node_id,
            "target": row.target_node_id,
            "relation": row.relation,
            "relation_label": row.relation_label,
            "directed": bool(row.directed),
            **({"importance": float(row.importance)} if row.importance is not None else {}),
            **({"source_refs": row.source_refs} if row.source_refs else {}),
        }
        for row in edges
    ]
    incoming = {edge["target"] for edge in snapshot_edges if edge["directed"]}
    roots = [node["id"] for node in snapshot_nodes if node["id"] not in incoming]
    return {
        "graph_id": graph.graph_id,
        "revision": int(graph.revision),
        "title": graph.title,
        "domain": graph.domain or "",
        "nodes": snapshot_nodes,
        "edges": snapshot_edges,
        "root_node_ids": roots,
    }
