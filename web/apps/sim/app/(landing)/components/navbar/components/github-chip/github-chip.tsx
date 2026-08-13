'use client'

import { ChipLink } from '@sim/emcn'
import { GithubOutlineIcon } from '@/components/icons'

/**
 * GitHub repository link - icon + star count, as on the old landing.
 *
 * Client leaf only so the icon component can be passed as a prop; the
 * star count itself is fetched server-side and arrives as a string.
 */

export function GitHubChip() {
  return (
    <ChipLink
      href='https://github.com/simstudioai/sim'
      target='_blank'
      rel='noopener noreferrer'
      leftIcon={GithubOutlineIcon}
      aria-label='GitHub ↗'
    >
      GitHub ↗
    </ChipLink>
  )
}
