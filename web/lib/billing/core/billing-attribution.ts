/** Trusted payer context attached to an execution by the API boundary. */
export interface BillingAttributionSnapshot {
  actorUserId: string
  workspaceId: string
  organizationId: string | null
  billedAccountUserId: string
  billingEntity: { type: 'user' | 'organization'; id: string }
  billingPeriod: { start: string; end: string }
  payerSubscription: {
    plan: string | null
    enterpriseWorkflowExecutionTimeoutSeconds?: number | null
  } | null
}
