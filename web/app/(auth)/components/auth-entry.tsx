'use client'

import { useSearchParams } from 'next/navigation'
import { Chip, ChipLink } from '@sim/emcn'
import { identityApi } from '@/lib/auth/identity-api'
import { isMockAuthEnabled } from '@/lib/core/config/env-flags'
import { AuthHeader, AuthLegalFooter } from './auth-shell'

type AuthKind = 'login' | 'register' | 'forgot-password'

const copy: Record<
  AuthKind,
  { title: string; description: string; action: string; legal: string }
> = {
  login: {
    title: '欢迎回来',
    description: '使用灵犀统一身份继续进入学习工作台',
    action: '继续登录',
    legal: '登录',
  },
  register: {
    title: '开始学习',
    description: '创建你的灵犀智学账户',
    action: '创建账户',
    legal: '注册',
  },
  'forgot-password': {
    title: '重置密码',
    description: '通过已验证邮箱安全恢复账户',
    action: '继续重置',
    legal: '继续',
  },
}

function safeCallback(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) {
    return '/workspace/lingxi/home/'
  }
  return value
}

export function AuthEntry({ kind }: { kind: AuthKind }) {
  const searchParams = useSearchParams()
  const content = copy[kind]
  const nextPath = safeCallback(searchParams.get('callbackUrl') ?? searchParams.get('callbackURL'))
  // The local Compose deployment has no browser-visible Identity cookie and
  // uses the fixed development principal. Keep this entry point aligned with
  // the other auth adapters instead of sending local users to the remote BFF.
  const target = isMockAuthEnabled ? nextPath : identityApi.authUrl(kind, nextPath)

  return (
    <div className='space-y-6'>
      <AuthHeader title={content.title} description={content.description} />
      <div className='flex justify-center'>
        <Chip
          variant='primary'
          className='h-9 min-w-[146px] text-sm'
          onClick={() => window.location.assign(target)}
        >
          {content.action}
        </Chip>
      </div>
      {kind === 'login' && (
        <div className='space-y-3 text-center text-sm'>
          <ChipLink
            href={identityApi.authUrl('forgot-password', nextPath)}
            prefetch={false}
            className='px-1 text-[var(--text-primary)]'
          >
            忘记密码？
          </ChipLink>
          <div className='flex items-center justify-center gap-2'>
            <span className='text-[var(--text-muted)]'>还没有账户？</span>
            <ChipLink
              href={`/signup?callbackUrl=${encodeURIComponent(nextPath)}`}
              className='px-1 text-[var(--text-primary)]'
            >
              注册
            </ChipLink>
          </div>
        </div>
      )}
      {kind === 'register' && (
        <div className='flex items-center justify-center gap-2 text-sm'>
          <span className='text-[var(--text-muted)]'>已有账户？</span>
          <ChipLink
            href={`/login?callbackUrl=${encodeURIComponent(nextPath)}`}
            className='px-1 text-[var(--text-primary)]'
          >
            登录
          </ChipLink>
        </div>
      )}
      {kind === 'forgot-password' && (
        <div className='text-center text-sm'>
          <ChipLink href='/login' className='px-1 text-[var(--text-primary)]'>
            返回登录
          </ChipLink>
        </div>
      )}
      <AuthLegalFooter action={content.legal} />
    </div>
  )
}
