# Sim source attribution

LingxiLearn's workspace shell, chat surface, resource panel, task composer, and
workflow canvas are adapted from the Sim open-source frontend:

- Upstream: [simstudioai/sim](https://github.com/simstudioai/sim/)
- Source snapshot: `ce2dff3cbabc65bd034aff117a2adbf03f86fde3`
- Relevant source: `apps/sim/app/workspace/[workspaceId]/home/`,
  `apps/sim/app/workspace/[workspaceId]/components/workspace-chrome/`,
  `apps/sim/app/workspace/[workspaceId]/w/components/sidebar/`,
  `apps/sim/app/workspace/[workspaceId]/w/[workflowId]/workflow.tsx`,
  `packages/workflow-renderer/src/workflow-block/workflow-block-view.tsx`, and
  `packages/emcn/src/components/button/button.tsx`,
  `packages/emcn/src/components/expandable/expandable.tsx`,
  `apps/sim/app/workspace/[workspaceId]/home/components/message-content/components/agent-group/agent-group.tsx`,
  `apps/sim/components/ui/shimmer-text.tsx`, and `apps/sim/hooks/use-smooth-text.ts`
- License: Apache License 2.0, as provided by the upstream repository

The Sim interaction primitives needed by this surface are vendored under
`web/components/sim/source/` and `web/hooks/use-smooth-text.ts`. The upstream
checkout is not modified and its backend or workspace data model is not used.
`web/lib/sim-adapter.ts` translates the existing LingxiGraph Agent Task snapshots
and SSE events into the Sim-derived UI model. Real task data is fetched from the
LingxiLearn API and real artifacts are rendered in the right-hand workspace.
