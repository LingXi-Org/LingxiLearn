# Merge policy

## Goal

Choose one existing learner graph only when the new learning context can be attached by a supported
curricular relation. Avoid giant graphs connected only by vague topic similarity.

## Decision order

1. If `graph_policy.mode=force_new`, choose `create_graph`.
2. If there are no existing graphs, choose `create_graph`.
3. If `preferred_graph_id` is present, inspect it first.
4. Search existing graphs for strong anchors:
   - same concept ID;
   - exact concept/alias equivalence;
   - explicit prerequisite/foundation/part-of/application relation supported by source material;
   - clear continuation of the same course unit with a defensible edge.
5. If exactly one graph has strong anchors, choose `extend_graph` or `update_graph`.
6. If the content is in the same broad subject but has no defensible edge, choose `create_graph`.
7. If two or more existing graphs are similarly plausible, do not join them. Prefer
   `create_graph` and explain the ambiguity in `warnings`.
8. If nothing new or better-supported is added, choose `no_change`.

## Extend vs update

Choose `extend_graph` when at least one node or edge is added.
Choose `update_graph` when no structural element is added and only node/edge metadata or learner
overlay changes.

## De-duplication

Reuse an existing node only if it denotes the same curriculum entity. Match in this order:

1. stable ID;
2. exact canonical label + compatible node type;
3. explicit alias;
4. unambiguous semantic identity supported by the supplied material.

Do not merge nodes solely because the names share a substring.

## Non-destructive v1

Do not delete nodes or edges. Do not automatically merge two existing graphs. If source material
appears to contradict an existing relation, emit a warning and leave destructive correction to the
host or a future audited migration flow.
