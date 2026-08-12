# Sim source attribution

LingxiLearn's workspace shell and task composer are adapted from the Sim open-source frontend:

- Upstream: [simstudioai/sim](https://github.com/simstudioai/sim/)
- Source snapshot: `ce2dff3cbabc65bd034aff117a2adbf03f86fde3`
- Relevant source: `apps/sim/app/workspace/[workspaceId]/home/home.tsx`,
  `apps/sim/app/workspace/[workspaceId]/home/components/user-input/`, and
  `apps/sim/app/workspace/[workspaceId]/components/workspace-chrome/`,
  `apps/sim/app/workspace/[workspaceId]/w/components/sidebar/`, and
  `packages/emcn/src/components/button/button.tsx`
- License: Apache License 2.0, as provided by the upstream repository

Only the local LingxiLearn adaptation is present in this repository. The upstream Sim
checkout is not modified; its backend, authentication, and workspace data model are
not imported. LingxiLearn continues to use its existing FastAPI REST/SSE contracts.
