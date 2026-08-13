import type { Metadata } from 'next'
import { buildLandingMetadata, withFilteredNoindex } from '@/lib/landing/seo'
import Careers from '@/app/(landing)/careers/careers'

/**
 * `team`/`location` render a genuinely different server-rendered job list (see
 * search-params.ts), so filtered URLs are noindexed rather than
 * self-canonicalized — same policy as the integrations/models/blog catalogs.
 */
export async function generateMetadata(): Promise<Metadata> {
  const base = buildLandingMetadata({
    title: 'Careers | Sim, the AI Workspace',
    description:
      'Join Sim, the open-source AI workspace where teams build, deploy, and manage AI agents. See open engineering, design, and go-to-market roles.',
    path: '/careers',
    keywords:
      'Sim careers, Sim jobs, AI workspace jobs, AI agent engineering jobs, open source jobs',
  })

  return withFilteredNoindex(base, false)
}

export default function Page() {
  return <Careers searchParams={Promise.resolve({})} />
}
