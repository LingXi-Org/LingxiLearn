import { selectRawMountableSecretNames } from '@/lib/credentials/secret-mount-options'
import { fetchWorkspaceEnvironment } from '@/lib/environment/api'
import { getQueryClient } from '@/app/_shell/providers/get-query-client'
import { environmentKeys, WORKSPACE_ENVIRONMENT_STALE_TIME } from '@/hooks/queries/environment'
import { workspaceCredentialKeys } from '@/hooks/queries/utils/credential-keys'
import {
  fetchWorkspaceCredentialList,
  WORKSPACE_CREDENTIAL_LIST_STALE_TIME,
} from '@/hooks/queries/utils/fetch-workspace-credentials'
import { getWorkflowListQueryOptions } from '@/hooks/queries/utils/workflow-list-query'
import { useWorkflowRegistry } from '@/stores/workflows/registry/store'

interface SubBlockOption {
  label: string
  id: string
}

/**
 * Loads the active workspace's workflows for multi-select subblocks
 * (`fetchOptions`). Set `excludeActiveWorkflow` for surfaces where selecting
 * the current workflow is meaningless (e.g. the Sim trigger never receives
 * events about itself).
 */
export async function fetchWorkspaceWorkflowOptions(options?: {
  excludeActiveWorkflow?: boolean
}): Promise<SubBlockOption[]> {
  const registry = useWorkflowRegistry.getState()
  const workspaceId = registry.hydration.workspaceId
  if (!workspaceId) return []

  const workflows = await getQueryClient().fetchQuery(
    getWorkflowListQueryOptions(workspaceId, 'active')
  )

  return workflows
    .filter(
      (workflow) => !options?.excludeActiveWorkflow || workflow.id !== registry.activeWorkflowId
    )
    .map((workflow) => ({ id: workflow.id, label: workflow.name }))
}

/**
 * Loads the active workspace's secret NAMES for the Function block's secret-scope
 * picker. Names only — values stay server-side and are injected at execution, the
 * same discipline the copilot's workspace context uses.
 *
 * Both halves come from the single workspace-environment response, which is the
 * client-side mirror of `getEffectiveDecryptedEnv` — the resolver the executor
 * injects from. Its `personal` slice is NOT the caller's raw personal variables:
 * under credential filtering it also carries personal secrets other members have
 * shared into the workspace, so reading `/api/environment` instead would hide
 * names the code can genuinely resolve. This is the same pair the `{{VAR}}`
 * autocomplete lists, so the picker and the editor never disagree.
 *
 * Values are masked to `''` for non-admin viewers; only the keys are used here.
 */
export async function fetchWorkspaceSecretNameOptions(): Promise<SubBlockOption[]> {
  const workspaceId = useWorkflowRegistry.getState().hydration.workspaceId
  if (!workspaceId) return []

  const environment = await getQueryClient().fetchQuery({
    queryKey: environmentKeys.workspace(workspaceId),
    queryFn: ({ signal }: { signal?: AbortSignal }) =>
      fetchWorkspaceEnvironment(workspaceId, signal),
    staleTime: WORKSPACE_ENVIRONMENT_STALE_TIME,
  })

  // Workspace entries shadow personal ones at execution (`getEffectiveDecryptedEnv`
  // spreads workspace last), but a name-only list just de-duplicates the union.
  const names = new Set<string>([
    ...Object.keys(environment?.workspace ?? {}),
    ...Object.keys(environment?.personal ?? {}),
  ])
  return [...names].sort().map((name) => ({ id: name, label: name }))
}

/** Loads only secret names the current actor may mount as plaintext into Copilot code. */
export async function fetchWorkspaceRawSecretNameOptions(): Promise<SubBlockOption[]> {
  const workspaceId = useWorkflowRegistry.getState().hydration.workspaceId
  if (!workspaceId) return []

  const credentials = await getQueryClient().fetchQuery({
    queryKey: workspaceCredentialKeys.list(workspaceId),
    queryFn: ({ signal }: { signal?: AbortSignal }) =>
      fetchWorkspaceCredentialList(workspaceId, signal),
    staleTime: WORKSPACE_CREDENTIAL_LIST_STALE_TIME,
  })

  return selectRawMountableSecretNames(credentials).map((name) => ({ id: name, label: name }))
}
