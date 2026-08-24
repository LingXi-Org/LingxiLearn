import type React from 'react'
import { AgentIcon, AgentSkillsIcon, McpIcon, WorkflowIcon } from '@/components/icons'
import { Repeat, Rows3 } from '@/components/ui-kit/icons'
import { PROVIDER_DEFINITIONS } from '@/providers/models'
import { normalizeToolId } from '@/tools/normalize'

/**
 * Stable span-type → icon/color presentation for trajectory and trace views.
 *
 * Replaces the former workflow block-registry lookups (`getBlock` /
 * `getBlockByToolName`): observability must not depend on the workflow editor
 * graph to explain an AgentRun/SkillRun. Sources are Lingxi-native only — the
 * provider registry for model spans, the product icon set for known runtime
 * span types — and anything unrecognized degrades to a stable neutral fallback.
 */

export const DEFAULT_SPAN_COLOR = '#6b7280'

export interface SpanPresentation {
  icon: React.ComponentType<{ className?: string }> | null
  bgColor: string
}

/**
 * Extracts the bare tool name from an MCP tool id of the form
 * `mcp-{serverId}-{toolName}`. Returns null when the id is not MCP-shaped.
 */
export function tryParseMcpToolName(toolId: string): string | null {
  if (!toolId.startsWith('mcp-')) return null
  const parts = toolId.split('-')
  if (parts.length < 3) return null
  const toolName = parts.slice(2).join('-')
  return toolName.length > 0 ? toolName : null
}

const MCP_SPAN_COLOR = '#dc2626'
const SKILL_SPAN_COLOR = '#8b5cf6'
const LOOP_SPAN_COLOR = '#6366f1'
const PARALLEL_SPAN_COLOR = '#14b8a6'
const WORKFLOW_SPAN_COLOR = '#6366f1'

/**
 * Resolves the presentation for one trajectory/trace span from its own
 * payload (`type`, `toolName`, `provider`) — never from the block registry.
 */
export function getSpanPresentation(
  type: string,
  toolName?: string,
  provider?: string
): SpanPresentation {
  const lowerType = type.toLowerCase()

  if (lowerType === 'tool' && toolName) {
    if (tryParseMcpToolName(toolName)) {
      return { icon: McpIcon, bgColor: MCP_SPAN_COLOR }
    }
    const normalized = normalizeToolId(toolName)
    if (normalized === 'load_skill') {
      return { icon: AgentSkillsIcon, bgColor: SKILL_SPAN_COLOR }
    }
    return { icon: null, bgColor: DEFAULT_SPAN_COLOR }
  }

  if (lowerType === 'loop' || lowerType === 'loop-iteration') {
    return { icon: Repeat, bgColor: LOOP_SPAN_COLOR }
  }
  if (lowerType === 'parallel' || lowerType === 'parallel-iteration') {
    return { icon: Rows3, bgColor: PARALLEL_SPAN_COLOR }
  }
  if (lowerType === 'workflow') {
    return { icon: WorkflowIcon, bgColor: WORKFLOW_SPAN_COLOR }
  }
  if (lowerType === 'model' && provider) {
    const providerDef = PROVIDER_DEFINITIONS[provider]
    if (providerDef?.icon) {
      return { icon: providerDef.icon, bgColor: providerDef.color ?? DEFAULT_SPAN_COLOR }
    }
  }
  if (lowerType === 'model' || lowerType === 'agent') {
    return { icon: AgentIcon, bgColor: DEFAULT_SPAN_COLOR }
  }
  return { icon: null, bgColor: DEFAULT_SPAN_COLOR }
}
