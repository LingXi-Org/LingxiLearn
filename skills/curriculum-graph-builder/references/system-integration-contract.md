# System integration contract

## Execution classification

This Skill is `phase=authoring`, `critical-path=false`, `learner-facing=false`,
`state-write-mode=proposal-only`, `parallel-safe=true`, and `latency-class=offline`. Treat it as a
bounded manager-as-tools capability invoked by a Supervisor or Course Pack pipeline. It may run in
parallel with lesson preparation, but it must never delay the learner's current teaching response.

## Recommended runtime flow

```text
course pack / trusted lesson event
        ↓
load learner graph candidates + learner-state signals
        ↓
curriculum-graph-builder
        ↓
validate result
        ↓
transactional patch applier (host)
        ↓
persist graph revision + audit event
        ↓
materialize KnowledgeGraphData
        ↓
KnowledgeGraphAnimation
```

Do **not** put this Skill on the learner critical path or send model output directly to the
visualization component before persistence. The host
must validate and apply the patch first, then return the canonical persisted snapshot.

## Input contract expected from LingxiLearn

Minimum request:

```json
{
  "schema_version": "curriculum-graph-builder-task.v1",
  "task_id": "turn_123",
  "learning_context": {
    "topic": "函数与导数",
    "source_materials": [
      {
        "source_id": "msg_123",
        "kind": "user_message",
        "content": "函数图像和导数应用之间有什么关系？"
      }
    ]
  },
  "existing_graphs": []
}
```

Production authoring requests should normally also include:

- relevant existing graph snapshots for the authenticated learner;
- current concept signals from the active learning session;
- concept-state signals from the authoritative learner-state layer;
- upstream lesson/assessment artifacts as source materials when they contain curriculum relations.

Do not pass unrelated private profile fields. Learner-state overlays are optional structured
signals; they do not turn this authoring Skill into a knowledge-tracing or tutoring agent.

Do not send unrelated private profile fields.

## Output handling

The Skill returns a patch, not the canonical database snapshot.

For `create_graph`:

1. host allocates `graph_id`;
2. accepts or remaps proposed node/edge IDs after collision checks;
3. applies all additions and overlay updates;
4. starts `revision=1` (or your chosen convention).

For `extend_graph` / `update_graph`:

1. require `decision.target_graph_id`;
2. compare `decision.base_revision` with the current DB revision;
3. if mismatched, reject with a revision conflict and rerun the Skill on fresh data;
4. apply patch atomically;
5. increment revision;
6. write an audit record containing `task_id`, old revision, new revision, and changed IDs.

For `no_change`, persist no graph mutation; an audit event may still be recorded.

## Persistence constraints

Recommended tables or equivalent document model:

```text
knowledge_graphs(
  graph_id, learner_id, title, domain, revision, created_at, updated_at
)
knowledge_graph_nodes(
  graph_id, node_id, label, type, importance, level, position_json,
  aliases_json, description, created_at, updated_at
)
knowledge_graph_edges(
  graph_id, edge_id, source_node_id, target_node_id,
  relation, relation_label, directed, importance, created_at, updated_at
)
knowledge_graph_learner_overlay(
  graph_id, learner_id, node_id, is_current, learning_state,
  evidence_ids_json, updated_at
)
knowledge_graph_events(
  event_id, learner_id, graph_id, task_id, base_revision, new_revision,
  patch_json, created_at
)
```

Keep curriculum structure separate from learner overlay even if the API joins them into one node
object for rendering.

## Candidate loading at scale

Do not send every graph in full forever. When the learner has large graphs, the host should first
retrieve 1–3 likely candidate graphs using graph title/domain/concept index, then send only those
snapshots to this Skill. This preserves the same contract while controlling context size.

## Frontend canonical response

Expose a persisted snapshot shaped approximately as:

```json
{
  "graph_id": "kg_math_analysis",
  "revision": 12,
  "title": "高等数学：函数与导数",
  "nodes": [
    {
      "id": "concept.function.definition",
      "label": "函数概念",
      "type": "concept",
      "importance": 0.9,
      "is_current": false,
      "learning_state": "demonstrated"
    }
  ],
  "edges": [
    {
      "id": "edge.function-to-graph",
      "source": "concept.function.definition",
      "target": "concept.function.graph",
      "relation": "foundation_for",
      "relation_label": "基础",
      "directed": true
    }
  ]
}
```
