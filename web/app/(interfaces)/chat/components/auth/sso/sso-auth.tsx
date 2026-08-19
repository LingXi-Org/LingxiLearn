'use client'

import { NotIntegrated } from '@/ee/not-integrated'

interface SSOAuthProps {
  identifier: string
}

/**
 * SSO is an enterprise-only deployment option. The open-source web build
 * still needs a typed, deterministic state for a deployed chat configured with
 * that option rather than importing an enterprise-only module that is absent
 * from this distribution.
 */
export default function SSOAuth({ identifier: _identifier }: SSOAuthProps) {
  return <NotIntegrated title='Single sign-on' />
}
