import { Suspense } from 'react'
import type { Metadata } from 'next'
import { buildLandingMetadata, withFilteredNoindex } from '@/lib/landing/seo'
import Pricing from '@/app/(landing)/pricing/pricing'

const TITLE = 'Pricing | Sim, the AI Workspace'
const DESCRIPTION =
  'Pricing for Sim, the open-source AI workspace for building, deploying, and managing AI agents. Compare the Free, Pro, Max, and Enterprise plans. Start free.'

/**
 * `billing` renders genuinely different prices server-side (see
 * search-params.ts), so the non-default variant is noindexed rather than
 * self-canonicalized — same policy as the integrations/models/blog catalogs.
 */
export async function generateMetadata(): Promise<Metadata> {
  const base = buildLandingMetadata({
    title: TITLE,
    description: DESCRIPTION,
    path: '/pricing',
    keywords:
      'Sim pricing, AI workspace pricing, AI agent platform pricing, build AI agents, Pro plan, Max plan, Enterprise plan, open-source AI agents, LLM pricing',
  })

  return withFilteredNoindex(base, false)
}

export default function Page() {
  return (
    <Suspense fallback={null}>
      <Pricing />
    </Suspense>
  )
}
