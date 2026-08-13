# Graph model

## Host-facing graph snapshot

After the host applies a patch and persists it, expose a full graph snapshot to the frontend:

```ts
type LearningState =
  | 'unknown'
  | 'not_observed'
  | 'emerging'
  | 'demonstrated'
  | 'misconception_evidence'
  | 'needs_recheck'

type KnowledgeNode = {
  id: string
  label: string
  type: 'domain' | 'topic' | 'concept' | 'skill' | 'method' | 'formula' |
        'example' | 'misconception' | 'application'
  importance: number
  is_current: boolean
  learning_state: LearningState
  level?: number
  position?: { x: number; y: number }
  aliases?: string[]
  description?: string
}

type Relation =
  | 'prerequisite_of'
  | 'foundation_for'
  | 'part_of'
  | 'leads_to'
  | 'applies_to'
  | 'contrasts_with'
  | 'commonly_confused_with'
  | 'related_to'

type KnowledgeEdge = {
  id: string
  source: string
  target: string
  relation: Relation
  relation_label: string
  directed: boolean
  importance?: number
}

type KnowledgeGraphData = {
  graph_id: string
  revision: number
  title: string
  domain?: string
  nodes: KnowledgeNode[]
  edges: KnowledgeEdge[]
  root_node_ids?: string[]
}
```

Your component can adapt this directly:

```tsx
<KnowledgeGraphAnimation
  data={{
    nodes: graph.nodes,
    edges: graph.edges.map(e => ({
      ...e,
      relation: e.relation_label,
    })),
  }}
/>
```

Keep the machine relation in storage; use `relation_label` for display.

## Relation direction semantics

| relation | direction semantics | label example |
|---|---|---|
| `prerequisite_of` | source must normally be understood before target | 先修 |
| `foundation_for` | source supports target but is not necessarily mandatory | 基础 |
| `part_of` | source is a component/subconcept of target | 属于 |
| `leads_to` | source naturally leads to target | 引出 |
| `applies_to` | source is applied to target | 应用于 |
| `contrasts_with` | symmetric contrast | 对比 |
| `commonly_confused_with` | symmetric confusion relation | 易混淆 |
| `related_to` | weak symmetric relation | 相关 |

For symmetric relations set `directed=false` even though `source` and `target` remain present for
storage and rendering APIs.

## Importance

`importance` is a curricular prior in `[0,1]`. It reflects how central the concept is to the current
curriculum and future dependencies. It is not a mastery score and should not encode weakness.

A host may later compute a display score, for example:

```text
display_importance = 0.7 * curricular_importance + 0.3 * normalized_graph_centrality
```

This computation belongs to the host, not this Skill.

## Learning-state rendering

Recommended UI interpretation:

- `unknown` / `not_observed`: neutral or faint;
- `emerging`: partially emphasized;
- `demonstrated`: stable/dark;
- `misconception_evidence`: weak-warning style;
- `needs_recheck`: review-warning style;
- `is_current=true`: current-focus ring or pulse independent of learning state.

A current node may simultaneously be `misconception_evidence` or `needs_recheck`.
