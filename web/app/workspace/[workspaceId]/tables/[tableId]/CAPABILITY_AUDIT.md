# Table Detail capability audit (#66)

Audited against `web/lib/lingxi/capabilities.ts`. A backend route counts only
when it belongs to the Lingxi product and has a Lingxi persistence owner; the
legacy Sim route tree is not a product owner.

| Capability | Previous UI entry | Previous frontend caller | Lingxi backend | Persistence owner | Real product caller | Class / result |
| --- | --- | --- | --- | --- | --- | --- |
| Table detail/read grid | Page and embedded table | Sim `useTable`; Lingxi `api.workspaceTable*` | `GET /api/table/{id}` and rows | `WorkspaceTable` | Page route, Mothership resource preview | A — retained on Lingxi client; arbitrary native/user columns remain visible |
| Workflow sidebar | Column/grid actions | workflow queries and table group mutations | None | None | None | B/C — closure deleted |
| WorkflowGroup | Grid schema/header identity | table group queries and workflow state queries | None | None | None | B — identity deleted |
| Enrichments sidebar | New-column menu | enrichment registry and group mutations | None | None | None | B — closure deleted |
| Enrichment details | Cell/action bar | enrichment detail query | None | None | None | B — closure deleted |
| Run status control | Header/options bar | table run-state and cancellation hooks | None | None | None | B — closure deleted |
| Run column / row | Grid/action bar | `useRunColumn` | None | None | None | B — closure deleted; no replacement backend invented |
| Column execution events | Table event stream | `useTableEventStream` | None | None | None | B — closure deleted |
| Execution details | Action bar/slideout | logs-by-workflow-execution query | None | None | None | B — closure deleted |
| Workflow execution | Grid headers/cells | workflow state/run clients | None | None | None | B — closure deleted |
| Saved views/filter/sort/layout | Detail options/grid | Sim table-view clients | `/api/table/{id}/views` | `WorkspaceTableView` | Native table API | A — native filter/sort projection and persisted views retained |
| Row/column mutation | Grid/context menus | Sim mutation clients | `/api/table/{id}/rows`, `/columns` | `WorkspaceTableRow` / `WorkspaceTableColumn` | Native table API | A — generic schema and writable row commands retained; read-only tables suppress mutation controls |
| Import/export | Page header/dialogs | Sim async CSV clients | `/api/table/{id}/export` and native row APIs | `WorkspaceTable*` | Native table API | A — native CSV export retained; Sim async-transfer UI deleted |
| Embedded mode | Mothership resource preview | `Table` | Same Lingxi table endpoints | `WorkspaceTable` | Mothership table artifact | A — shares `useTableDetailController` with page mode |

The Lingxi capability manifest marks editable workflows `not_integrated`. Table
Detail therefore removes workflow execution while retaining the native WorkspaceTable projection and its generic schema. Agent
execution remains represented by canonical AgentTask/AgentTaskEvent surfaces;
Table Detail does not translate those identities into a WorkflowGroup facade.
