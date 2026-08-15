# Sim workspace source baseline

This directory contains the native Sim workspace source closure imported from
Sim v0.8.0 at commit `48c59c8a` (the fixed
implementation baseline for this migration). Sim is distributed under the
Apache License 2.0; the upstream notice is retained in
[`NOTICE`](./NOTICE).

## Imported surfaces

- Workspace chrome and task history / Home (Mothership) chat
- Files, folders, previews and text editors
- Tables, views, filters, CSV/TSV import and export
- Knowledge bases, documents, chunks, tags and search
- Logs and read-only execution/audit details
- System and personal Skills
- Account, learning preferences and private workspace appearance settings
- Account security/session management through LingxiIdentity; legacy and v2
  billing/usage contracts are read-only internal-plan adapters, while team
  administration remains an explicit placeholder because Lingxi workspaces
  have no payment provider or members.

The native Sim components, hooks, stores, contracts and UI packages remain in
the source tree. Lingxi-specific changes are isolated to `lib/lingxi`, the
workspace host provider/sidebar, the API transport adapter and the FastAPI
workspace routes.

## Deliberate local differences

1. `lingxi` is the only public workspace slug. The backend resolves it to the
   authenticated learner's private singleton workspace.
2. LingxiIdentity owns the browser session. Next proxies `/api`, `/auth` and
   `/api/v1` to FastAPI through `LINGXILEARN_API_ORIGIN`.
3. LingxiGraph task events replace Sim's workflow chat transport. Resource
   references and skill snapshots are carried on task requests.
4. Native workflow editor/CRUD, canvas, deployment, schedules, workflow
   columns, enrichment, dispatch and connector source are restored from the
   pinned Sim tag. Their adaptation to the current LingxiLearn/FastAPI/
   LingxiGraph interfaces is intentionally deferred.
5. Realtime collaboration is disabled. File editing is single-writer and table
   updates use the HTTP API; no Yjs, Socket.IO, Redis or S3 service is added.

## Upgrade procedure

When upgrading Sim, update the pinned commit and the manifest in the same
change, then re-run the native source-closure checks. Keep backend adaptation
separate while the underlying interfaces are being reworked.
