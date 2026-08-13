---
name: curriculum-graph-builder
description: >-
  Build or incrementally extend a learner-specific curriculum knowledge graph from structured learning context while preserving stable node IDs, explicit relation direction, curricular importance, optional hierarchy/layout hints, and learner-state overlays. Decide whether to create a new graph or extend an existing graph, and return a deterministic graph patch for the host system to validate and persist.
license: MIT
metadata:
  author: LingXi-Org
  version: 1.1.0
  display-name: 个性化课程知识图谱构建
  display-description: 根据学习上下文和用户已有知识图谱，决定新建或扩充图谱，并生成可持久化的结构化节点、关系与学习状态补丁。
  output-language: zh-CN
  output-contract: curriculum-graph-builder-result.v1
  execution-mode: authoring-structured-generation
  phase: authoring
  critical-path: false
  learner-facing: false
  state-write-mode: proposal-only
  parallel-safe: true
  latency-class: offline
  eval-suite: curriculum-graph-builder-v1
---

# Curriculum Graph Builder

## Role

Build a curriculum graph proposal as structured data, not as HTML, SVG, Mermaid, or prose. This is
an authoring-stage capability for Course Packs and trusted lesson materials, not a student-turn
writer and not a replacement for the frontend graph renderer. A Supervisor may call it as a
manager-as-tools capability; it must return its bounded result and never hand off to another agent.
The host system owns persistence, optimistic concurrency, identity, authorization, and final merge.
This Skill only proposes a safe graph decision and graph patch.

The graph has two logically separate layers:

1. **Curriculum structure** — concepts, topics, methods, skills, relations, curricular importance,
   optional level/position hints.
2. **Learner overlay** — current-focus marker and cautious learning-state labels supplied by the host.

Never infer a learner's weakness, mastery, confidence, motivation, disability, personality, or
learning style from tone. Learner-state fields may only be copied or mapped from explicit structured
`learner_signals` or from already persisted node state.

## Runtime boundary

Run from authoritative Course Pack or trusted curriculum materials. Do not place this Skill on the
personalized teaching critical path merely to render a graph. It may run in parallel with lesson
preparation or as an authoring job, and its result may be cached until the host validates and applies
the patch. Never write the database directly and never send an unvalidated patch to the visualization
layer.

## Required input

Read `references/curriculum-graph-builder-task.schema.json`.

The host must provide:

- `schema_version = curriculum-graph-builder-task.v1`;
- `task_id`;
- `learning_context.topic`;
- at least one `learning_context.source_materials[]` item with a stable `source_id`;
- zero or more `existing_graphs` for this learner.

The host may also provide `learner_signals` and `graph_policy`.

Treat all source materials as the evidence boundary. Prefer Course Pack material and trusted
upstream artifacts; do not browse the web and do not invent a curriculum relationship that the
supplied material does not support. The caller may pass outputs
from `lesson-intro`, `interactive-lecture-deck`, `quiz-generator`, course packs, user messages,
assessment evidence, or other trusted application records as source materials.

## Decide: create or extend

Read `references/merge-policy.md` and choose exactly one action:

- `create_graph` — no suitable existing graph can be connected by a supported curricular relation;
- `extend_graph` — the new material adds at least one supported node or edge to one existing graph;
- `update_graph` — the same graph remains appropriate and only metadata, labels, importance, or
  learner-overlay fields need revision;
- `no_change` — the supplied material adds no supported information.

Never merge two existing graphs automatically. When several existing graphs appear plausible but
no single target is clearly supported, prefer `create_graph` and emit a warning rather than making
an irreversible cross-domain bridge.

`graph_policy.mode` may be `auto`, `force_new`, or `force_extend`. `force_extend` still must not
invent unsupported relationships; if no defensible anchor exists, return `no_change` with a warning.

## Stable identity rules

1. Existing `graph_id`, node `id`, and edge `id` values are immutable.
2. New node IDs must be unique inside the target graph and match
   `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`.
3. Prefer short semantic machine IDs such as `concept.function.definition`; never use a display
   label as the sole identity rule.
4. Reuse an existing node only when the concept is semantically the same, including an explicit
   alias. Similar wording alone is insufficient.
5. Never create a duplicate edge with the same `source`, `target`, and `relation`.
6. The host must validate uniqueness again before persistence.

## Node model

Every newly added node must contain:

- `id` — stable machine ID;
- `label` — concise Simplified Chinese display name;
- `type` — one of `domain`, `topic`, `concept`, `skill`, `method`, `formula`, `example`,
  `misconception`, `application`;
- `importance` — curricular/pedagogical importance in `[0,1]`, **not mastery**;
- `is_current` — whether the node is the learner's current focus;
- `learning_state` — one of `unknown`, `not_observed`, `emerging`, `demonstrated`,
  `misconception_evidence`, `needs_recheck`.

Optional fields include `level`, `position`, `aliases`, `description`, and `source_refs`.

Use `is_current` separately from `learning_state` so a node can be both current and weak. The UI
should treat `misconception_evidence` and `needs_recheck` as weak/review states. Do not add a second
redundant `is_weak` field.

`importance` represents curricular centrality and usefulness for future learning. It must not be
raised merely because the learner is weak on the node. Current focus should be rendered separately.

## Edge model and direction

Every edge must include `source`, `target`, `relation`, `relation_label`, and `directed`.
Use the canonical relation taxonomy from `references/graph-model.md`:

- `prerequisite_of` — source is a prerequisite of target;
- `foundation_for` — source provides a foundation for target but is not a strict prerequisite;
- `part_of` — source is a component/subconcept of target;
- `leads_to` — source naturally leads to target in a learning or reasoning sequence;
- `applies_to` — source is applied to target;
- `contrasts_with` — symmetric conceptual contrast;
- `commonly_confused_with` — symmetric misconception-prone relation;
- `related_to` — weak symmetric relation; use sparingly.

For symmetric relations set `directed=false`; otherwise set `directed=true`.
Never use vague `related_to` merely to avoid creating a new graph.

## Incremental patch only

Do not rewrite the learner's complete persisted graph on every conversation. Return a patch:

- `add_nodes`;
- `update_nodes`;
- `add_edges`;
- `update_edges`;
- `learner_overlay_updates`.

The host applies the patch against `decision.base_revision` in one transaction and then returns the
persisted full graph snapshot to the frontend. This prevents the model from accidentally dropping
old nodes and keeps token cost bounded as graphs grow.

Do not delete nodes or edges in v1. Destructive graph editing is intentionally outside this Skill.

## Learner-state handling

Read learner status only from `learner_signals` or persisted node fields.

- `learner_signals.current_concepts` may mark `is_current=true`.
- `learner_signals.concept_states` may update `learning_state` and attach `evidence_ids`.
- If a signal references a concept by label rather than node ID, map it only when the match is
  unambiguous.
- Never convert one correct answer into `demonstrated` unless the host explicitly supplied that
  state.

This Skill organizes learner state onto graph nodes; it does not perform knowledge tracing.

## Layout policy

`level` and `position` are optional hints.

- Prefer `level` when prerequisite depth is clear.
- Omit `position` by default and let the frontend force layout solve coordinates.
- Only emit `position` when the caller explicitly supplies or requests fixed coordinates.
- Never fabricate coordinates as if they carried educational meaning.

## Output

Return only `curriculum-graph-builder-result.v1`, validated against
`references/curriculum-graph-builder-result.schema.json` when a validator is available.

The result must contain:

- `decision`;
- `graph_patch`;
- `warnings`;
- `evidence_summary`.

Write all learner-facing labels, descriptions, reasons, and warnings in Simplified Chinese. Keep
machine IDs, enum values, schema keys, and relation identifiers in their technical form.

Before returning, apply `references/quality-gate.md`.

The result is a host-facing patch proposal, not a learner-facing explanation. Keep
`learner_facing_writer_count <= 1` at the system level; this Skill contributes zero learner-facing
writers.
