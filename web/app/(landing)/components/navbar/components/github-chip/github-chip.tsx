'use client'

import { GithubOutlineIcon } from '@/components/icons'
import { ChipLink } from '@/components/ui-kit'

/**
 * GitHub repository link - icon + star count, as on the old landing.
 *
 * Client leaf only so the icon component can be passed as a prop; the
 * star count itself is fetched server-side and arrives as a string.
 */

export function GitHubChip() {
  return (
    <ChipLink
      href='https://github.com/LingXi-Org/LingxiGraph'
      target='_blank'
      rel='noopener noreferrer'
      leftIcon={GithubOutlineIcon}
      aria-label='GitHub ↗'
    >
      GitHub ↗
    </ChipLink>
  )
}
