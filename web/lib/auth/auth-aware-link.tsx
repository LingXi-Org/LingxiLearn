'use client'

import type { ComponentProps } from 'react'
import { ChipLink } from '@/components/ui-kit'
import { useSession } from './session-provider'

type Props = Omit<ComponentProps<typeof ChipLink>, 'href'> & {
  href?: string
  authenticatedHref?: string
}

/** A CTA that resolves to the workspace for an already authenticated user. */
export function AuthAwareChipLink({
  href = '/signup',
  authenticatedHref,
  onClick,
  ...props
}: Props) {
  const { authenticated, ready } = useSession()
  const shouldUseAuthenticatedTarget = authenticatedHref !== undefined || href === '/signup'
  const target =
    ready && authenticated && shouldUseAuthenticatedTarget ? (authenticatedHref ?? '/workspace') : href

  return (
    <ChipLink
      {...props}
      href={target}
      prefetch={false}
      onClick={(event) => {
        if (ready && authenticated && shouldUseAuthenticatedTarget) {
          event.preventDefault()
          window.location.assign(authenticatedHref ?? '/workspace')
        }
        onClick?.(event)
      }}
    />
  )
}
