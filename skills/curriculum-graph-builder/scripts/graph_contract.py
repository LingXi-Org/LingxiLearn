#!/usr/bin/env python3
"""Contract helper for curriculum-graph-builder.

No network or database access. The host must authorize script execution independently.
Commands:
  validate-task <json>
  validate-result <json>
  apply-patch <graph.json> <result.json> <out.json>
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

try:
    import jsonschema
except Exception:  # optional dev dependency
    jsonschema = None

HERE = Path(__file__).resolve().parent.parent
REF = HERE / "references"


def load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(instance, schema_name: str):
    schema = json.loads((REF / schema_name).read_text(encoding="utf-8"))
    if jsonschema is None:
        raise SystemExit("jsonschema is required for schema validation")
    jsonschema.Draft202012Validator(schema).validate(instance)


def semantic_checks_result(result, existing_graph=None):
    patch = result["graph_patch"]
    added_nodes = patch["add_nodes"]
    added_edges = patch["add_edges"]
    node_ids = [n["id"] for n in added_nodes]
    edge_ids = [e["id"] for e in added_edges]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("duplicate node id in add_nodes")
    if len(edge_ids) != len(set(edge_ids)):
        raise ValueError("duplicate edge id in add_edges")

    known_nodes = set(node_ids)
    known_edges = set(edge_ids)
    edge_triples = set()
    if existing_graph:
        known_nodes |= {n["id"] for n in existing_graph.get("nodes", [])}
        known_edges |= {e["id"] for e in existing_graph.get("edges", [])}
        edge_triples |= {(e["source"], e["target"], e["relation"]) for e in existing_graph.get("edges", [])}
        collision_nodes = {n["id"] for n in added_nodes} & {n["id"] for n in existing_graph.get("nodes", [])}
        collision_edges = {e["id"] for e in added_edges} & {e["id"] for e in existing_graph.get("edges", [])}
        if collision_nodes:
            raise ValueError(f"new node ids collide with existing graph: {sorted(collision_nodes)}")
        if collision_edges:
            raise ValueError(f"new edge ids collide with existing graph: {sorted(collision_edges)}")

    for e in added_edges:
        if e["source"] == e["target"]:
            raise ValueError(f"self-loop not allowed: {e['id']}")
        if e["source"] not in known_nodes or e["target"] not in known_nodes:
            raise ValueError(f"edge references unknown node: {e['id']}")
        triple = (e["source"], e["target"], e["relation"])
        if triple in edge_triples:
            raise ValueError(f"duplicate semantic edge: {triple}")
        edge_triples.add(triple)

    for u in patch["update_nodes"]:
        if u["id"] not in known_nodes:
            raise ValueError(f"update_nodes references unknown node: {u['id']}")
    for u in patch["update_edges"]:
        if u["id"] not in known_edges:
            raise ValueError(f"update_edges references unknown edge: {u['id']}")
    for u in patch["learner_overlay_updates"]:
        if u["node_id"] not in known_nodes:
            raise ValueError(f"overlay references unknown node: {u['node_id']}")


def apply_patch(graph, result):
    out = deepcopy(graph)
    decision = result["decision"]
    if decision["action"] == "no_change":
        return out
    if decision["action"] in {"extend_graph", "update_graph"}:
        if out.get("graph_id") != decision["target_graph_id"]:
            raise ValueError("target_graph_id mismatch")
        if out.get("revision") != decision["base_revision"]:
            raise ValueError("revision conflict")

    semantic_checks_result(result, out)
    patch = result["graph_patch"]
    nodes = {n["id"]: deepcopy(n) for n in out.get("nodes", [])}
    edges = {e["id"]: deepcopy(e) for e in out.get("edges", [])}

    for n in patch["add_nodes"]:
        nodes[n["id"]] = deepcopy(n)
    for u in patch["update_nodes"]:
        nodes[u["id"]].update(deepcopy(u["set"]))
    for e in patch["add_edges"]:
        edges[e["id"]] = deepcopy(e)
    for u in patch["update_edges"]:
        edges[u["id"]].update(deepcopy(u["set"]))
    for u in patch["learner_overlay_updates"]:
        n = nodes[u["node_id"]]
        if "is_current" in u:
            n["is_current"] = u["is_current"]
        if "learning_state" in u:
            n["learning_state"] = u["learning_state"]

    out["nodes"] = list(nodes.values())
    out["edges"] = list(edges.values())
    if decision.get("proposed_title"):
        out["title"] = decision["proposed_title"]
    if decision.get("proposed_domain"):
        out["domain"] = decision["proposed_domain"]
    out["revision"] = int(out.get("revision", 0)) + 1
    return out


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    cmd = argv[1]
    if cmd == "validate-task":
        obj = load(argv[2])
        validate(obj, "curriculum-graph-builder-task.schema.json")
        print("OK")
    elif cmd == "validate-result":
        obj = load(argv[2])
        validate(obj, "curriculum-graph-builder-result.schema.json")
        semantic_checks_result(obj)
        print("OK")
    elif cmd == "apply-patch":
        if len(argv) != 5:
            raise SystemExit("apply-patch <graph.json> <result.json> <out.json>")
        graph = load(argv[2])
        result = load(argv[3])
        validate(result, "curriculum-graph-builder-result.schema.json")
        out = apply_patch(graph, result)
        Path(argv[4]).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(argv[4])
    else:
        raise SystemExit(f"unknown command: {cmd}")


if __name__ == "__main__":
    main(sys.argv)
