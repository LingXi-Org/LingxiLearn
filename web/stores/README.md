# Client state ownership

Zustand stores in this directory hold feature-local client state only. Server entities remain
canonical in API contracts and TanStack Query; domain types live under `lib/` or their feature.

| Store | Scope | Persistence | Reset lifecycle |
| --- | --- | --- | --- |
| `browser-session` | chat/desktop scope | none | discarded with a chat; all scopes reset on workspace switch/logout |
| `copilot-terminal` | chat/desktop scope | none | discarded with a chat; all scopes reset on workspace switch/logout |
| `folders` | active workspace UI selection | none | reset on workspace switch/logout |
| `logs` | logs view/filter UI | `log-details-ui-state` | local preference; cleared on logout |
| `mothership-drafts` | `workspaceId:threadId` | localStorage `mothership-drafts:v1` | scoped by key; all drafts reset on logout |
| `mothership-queue` | task or pending workspace task | sessionStorage `mothership-queue` | task migration/clear; memory and storage reset on logout |
| `operation-queue` | active workflow collaboration | none | reset on workspace switch/logout |
| `settings` | unsaved-settings UI | none | component lifecycle |
| `sidebar` | workspace chrome preference | localStorage `sidebar-state` | width is user preference; cleared on logout |
| `table` | table undo/import UI | none | table lifecycle |
| `tool-permission` | active permission card UI | none | component/task lifecycle |
| `variables` | active workflow editor draft | none | workflow/workspace lifecycle |
| `workflows` | active editor draft, selection, clipboard | none | workflow/workspace switch and logout |

Persistent storage must never contain unscoped user data. Any new persistent store must document
its key, scope, migration version, and logout/reset owner in this table.
