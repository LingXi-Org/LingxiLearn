/**
 * Everything that runs inside the isolated-vm pool lives in one of two tiers.
 * This file is the single grep surface for "what user code can execute in the
 * sandbox" — if you are adding a new place that spawns into the isolate,
 * register it below and/or extend one of the two tiers.
 *
 * Tier 1 — Sandbox tasks (this folder).
 *   Bytes-producing tasks with a fixed input shape (`{ workspaceId, code }`),
 *   pre-loaded library bundles, and a host-side broker set. User code is
 *   trusted to the extent that our bootstrap + finalize wrap every execution.
 *   Invoked via `runSandboxTask(id, input, options?)`.
 *     - `pptx-generate`  → `apps/sim/sandbox-tasks/pptx-generate.ts`
 *     - `docx-generate`  → `apps/sim/sandbox-tasks/docx-generate.ts`
 *     - `pdf-generate`   → `apps/sim/sandbox-tasks/pdf-generate.ts`
 *
 * E2B-routed executions (untrusted workflow runs) are a separate runtime
 * entirely and are not part of this registry.
 */

export { docxGenerateTask } from '@/sandbox-tasks/docx-generate'
export { pdfGenerateTask } from '@/sandbox-tasks/pdf-generate'
export { pptxGenerateTask } from '@/sandbox-tasks/pptx-generate'
export { getSandboxTask, SANDBOX_TASKS, type SandboxTaskId } from '@/sandbox-tasks/registry'
