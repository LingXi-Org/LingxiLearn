# `web/lib` ownership and reachability

`web/lib` is application code, not an upstream archive. A top-level directory
must be owned by a current LingxiLearn capability and reachable from a deployed
entrypoint. Git history is the only home for retired Sim implementations.

Core ownership boundaries:

- `lingxi`, `mothership`: Lingxi chat and canonical event presentation.
- `api`: browser/server transport contracts and route adapters.
- `auth`, `permissions`, `workspaces`: identity and tenancy.
- `workspace-files`, `knowledge`, `table`: learner content and data.
- `execution`, `tools`, `workflows`: retained workflow/runtime compatibility.
- `core`, `environment`, `logger`, `monitoring`, `utils`: shared platform code.

Run `bun run audit:lib-reachability` to produce the current machine-readable
inventory. The graph starts from Next special entry files, Trigger background
jobs, proxy/instrumentation files, deployment configs, and separately reported
operational scripts. It follows static
imports, literal dynamic imports (including webpack-commented imports), and
CommonJS `require`/`require.resolve` calls. The report includes unresolved
dynamic imports so they cannot silently justify deletion.

Known non-literal imports are allowlisted by file and expression with a reason;
the audit fails closed when a new unresolved dynamic import appears.
Deterministically generated API contracts are classified explicitly instead of
being mistaken for dead source; `check:contracts` verifies their freshness.

Every surviving top-level directory must also have an entry in
`ownership.json`. The audit fails when an owner/capability entry is missing or
stale, so adding a new upstream-shaped directory cannot silently expand the
application boundary.

Classifications mean:

- `production-reachable`: at least one file is in the deployed entry graph.
- `test-only`: no deployed path reaches the directory, but tests do.
- `unreachable`: neither deployed entries nor tests reach it.

`test-only` does not grant production ownership. Delete a self-contained
implementation and its tests together; move a genuinely reusable test helper
under the consuming test tree. A directory with any reachable file still needs
file-level review because the report deliberately shows sample files and counts
rather than declaring its whole subtree live.

The audit fails when a non-test implementation is reachable only from tests.
Ordinary `*.test.*` and `*.spec.*` files remain valid, but they cannot keep a
production-shaped business implementation alive on their own.

Migration readers must state an owner and executable deletion condition beside
their implementation. Currently `lingxi/legacy/v0` is owned by Lingxi chat; its
deletion condition is documented in that module and its production usage is
recorded by the AgentTask event API.

Top-level compatibility domains must also declare a concrete deletion condition
in `ownership.json`. This is a migration ledger, not permanent ownership.
