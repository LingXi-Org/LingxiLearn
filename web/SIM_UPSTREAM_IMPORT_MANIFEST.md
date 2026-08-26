# Sim v0.8.0 import manifest

Baseline: `48c59c8a` (fixed; no floating upstream branch).

| Source closure | Lingxi destination | Status |
| --- | --- | --- |
| `apps/sim/app/workspace/[workspaceId]/home` | `web/app/workspace/[workspaceId]/home` | imported, LingxiGraph adapter |
| `apps/sim/app/workspace/[workspaceId]/files` | `web/app/workspace/[workspaceId]/files` | imported, FastAPI files API |
| `apps/sim/app/workspace/[workspaceId]/tables` | `web/app/workspace/[workspaceId]/tables` | imported, non-workflow columns only |
| `apps/sim/app/workspace/[workspaceId]/knowledge` | `web/app/workspace/[workspaceId]/knowledge` | imported, native document management only; connector closure removed |
| `apps/sim/app/workspace/[workspaceId]/logs` | `web/app/workspace/[workspaceId]/logs` | imported, read-only Lingxi activity |
| `apps/sim/app/workspace/[workspaceId]/skills` | `web/app/workspace/[workspaceId]/skills` | imported, system/personal skills |
| `apps/sim/app/workspace/[workspaceId]/settings` | `web/app/workspace/[workspaceId]/settings` | imported, account/preferences only |
| `apps/sim/app/account/settings` | `web/app/account/settings` | replaced by the LingxiIdentity-backed profile, security, and device-session center; billing/team contracts removed |
| `apps/sim/packages/*` | `web/packages/*` | imported dependency closure |
| `apps/sim/components/ui` | `web/components/ui` | imported shared UI closure |

Excluded from the product closure:

- `/w` editor pages and workflow sidebar sections
- workflow create/update/delete/import/export/deploy/schedule APIs
- workflow columns, enrichment and dispatch APIs
- workflow MCP/connector/member/invitation/collaboration surfaces
- static-export HTML fallback and FastAPI web serving

Compatibility modules that remain under non-routable source paths only satisfy
read-only log rendering or shared text-input helpers. They do not register a
route, workflow resource, mutation or editable canvas.
