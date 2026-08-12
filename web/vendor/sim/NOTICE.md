# Sim source attribution

LingxiLearn's workspace shell, chat surface, resource panel, and task composer are
adapted from the Sim open-source frontend:

- Upstream: [simstudioai/sim](https://github.com/simstudioai/sim/)
- Source snapshot: `ce2dff3cbabc65bd034aff117a2adbf03f86fde3`
- Relevant source: `apps/sim/app/workspace/[workspaceId]/home/home.tsx`,
  `apps/sim/app/workspace/[workspaceId]/home/components/user-input/`, and
  `apps/sim/app/workspace/[workspaceId]/home/components/message-content/`,
  `apps/sim/app/workspace/[workspaceId]/home/components/mothership-chat/`,
  `apps/sim/app/workspace/[workspaceId]/components/workspace-chrome/`,
  `apps/sim/app/workspace/[workspaceId]/w/components/sidebar/`, and
  `packages/emcn/src/components/button/button.tsx`
- License: Apache License 2.0, as provided by the upstream repository

Only the local LingxiLearn adaptation is present in this repository. The upstream Sim
checkout is not modified; its backend, authentication, and workspace data model are
not imported. `web/lib/sim-adapter.ts` translates the existing LingxiGraph REST/SSE
snapshots and events into the Sim-derived client model for future integration. The
application currently runs `web/lib/sim-mock.ts` instead: it renders a deterministic
local placeholder Agent, orchestration graph, tools, sub-agents, and resources
without calling a real API.

Unsupported Sim resources (tables, files, knowledge bases, integrations, schedules,
attachments, voice input, and skills) are listed in the native capability placeholder
panel or rendered as disabled controls. The client does not claim that this local
mock state came from LingxiGraph.
