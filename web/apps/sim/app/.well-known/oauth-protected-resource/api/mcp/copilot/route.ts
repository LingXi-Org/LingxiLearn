import type { NextResponse } from 'next/server'
import { copilotMcpDeprecatedResponse } from '@/lib/mcp/copilot-deprecated'

export const dynamic = 'force-static'
export const revalidate = 3600

export async function GET(): Promise<NextResponse> {
  return copilotMcpDeprecatedResponse()
}
