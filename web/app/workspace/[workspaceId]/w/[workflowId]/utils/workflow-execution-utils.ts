/** Workflow execution is intentionally unavailable in the Lingxi workspace. */
export async function executeWorkflowWithFullLogging(
  ..._args: any[]
): Promise<Record<string, unknown>> {
  throw new Error('Editable workflow execution is not available in Lingxi')
}
