/**
 * Correlation metadata shared by execution logs and workflow execution context.
 *
 * The former async-job queue lived in this module, but the current execution
 * paths no longer enqueue webhook jobs. Keeping the correlation shape here
 * preserves the stable import used by logs and executors without retaining a
 * dead queue abstraction.
 */
export type AsyncExecutionCorrelationSource =
  | 'workflow'
  | 'schedule'
  | 'webhook'
  | 'custom_block'
  | 'workflow_group'

export interface AsyncExecutionCorrelation {
  executionId: string
  requestId: string
  source: AsyncExecutionCorrelationSource
  workflowId: string
  /** Server-validated binding for a browser-routed Copilot workflow tool execution. */
  copilotToolCallId?: string
  triggerType?: string
  webhookId?: string
  scheduleId?: string
  path?: string
  provider?: string
  scheduledFor?: string
  tableId?: string
  rowId?: string
  groupId?: string
  /**
   * Workspace of the invoking run. Set for custom-block children, whose invoker
   * lives in a different workspace than the log row this correlation lands on.
   */
  invokerWorkspaceId?: string
}

export interface WorkflowGroupExecutionCorrelation extends AsyncExecutionCorrelation {
  source: 'workflow_group'
  tableId: string
  rowId: string
  groupId: string
}
