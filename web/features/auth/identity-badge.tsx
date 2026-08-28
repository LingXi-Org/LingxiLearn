'use client'

import { useEffect, useState } from 'react'
import { type Identity, identityApi } from '@/shared/api/client'

export function IdentityBadge() {
  const [identity, setIdentity] = useState<Identity | null>(null)

  useEffect(() => {
    identityApi
      .me()
      .then(setIdentity)
      .catch(() => setIdentity(null))
  }, [])

  if (!identity) return <a href='/login'>Sign in</a>
  return <span className='identity-badge'>{identity.name ?? identity.email ?? 'Learner'}</span>
}
