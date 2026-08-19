import type { CostLedger } from '@/lib/api/contracts/logs'
import { apportionCredits, dollarsToCredits } from '@/lib/billing/credits/conversion'

/**
 * Cost projection for the run-detail surface. Sourced solely from the
 * usage_log ledger (single source of truth): line items (Base Run / per-model /
 * per-integration) get integer credits apportioned with a single round at the
 * total so rows always reconcile. Pre-ledger runs that only carry the
 * cost_total projection show the total alone — no itemization.
 */
export interface RunCostBreakdown {
  rows: Array<{ key: string; label: string; credits: number; dollars: number }>
  totalCredits: number
  totalDollars: number
  tokens: { input: number; output: number }
}

export function projectRunCost(
  costLedger: CostLedger | null,
  costTotalDollars: number | null
): RunCostBreakdown | null {
  if (costLedger && costLedger.items.length > 0) {
    const credits = apportionCredits(
      costLedger.items.map((item, i) => ({ key: String(i), dollars: item.cost }))
    )
    const rows = costLedger.items.map((item, i) => ({
      key: String(i),
      label:
        item.category === 'fixed' && item.description === 'execution_fee'
          ? 'Base Run'
          : item.description,
      credits: credits[String(i)] ?? 0,
      dollars: item.cost,
    }))
    return {
      rows,
      totalCredits: dollarsToCredits(costLedger.total),
      totalDollars: costLedger.total,
      tokens: {
        input: costLedger.items.reduce((s, it) => s + (it.inputTokens ?? 0), 0),
        output: costLedger.items.reduce((s, it) => s + (it.outputTokens ?? 0), 0),
      },
    }
  }

  // Total-only (pre-ledger runs with just the cost_total projection).
  if (costTotalDollars == null) return null
  return {
    rows: [],
    totalCredits: dollarsToCredits(costTotalDollars),
    totalDollars: costTotalDollars,
    tokens: { input: 0, output: 0 },
  }
}
