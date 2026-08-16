'use client'

import { useSearchParams } from 'next/navigation'
import { Chip, ChipLink } from '@sim/emcn'
import {
  startLogin,
  startRegistration,
} from '@/lib/auth/auth-client'
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

export function AuthEntry({
  kind,
  registrationDisabled = false,
}: {
  kind: AuthKind
  registrationDisabled?: boolean
}) {
  const searchParams = useSearchParams()
  const content = copy[kind]
  const nextPath = safeCallback(
    searchParams.get('callbackUrl') ??
      searchParams.get('callbackURL') ??
      searchParams.get('redirect')
  )

  const start = () => {
    if (kind === 'login') return startLogin({ callbackURL: nextPath })
    if (kind === 'register') return startRegistration({ callbackURL: nextPath })
    // Forgot-password is already a Logto Experience route. The entry is only
    // used for the login and registration pages, but keeping this branch makes
    // the component safe to reuse for a future local status screen.
    return Promise.resolve()
  }

  return (
    <div className='space-y-6'>
      <AuthHeader title={content.title} description={content.description} />
      <div className='flex justify-center'>
        <Chip
          variant='primary'
          className='h-9 min-w-[146px] text-sm'
          onClick={() => void start()}
        >
          {content.action}
        </Chip>
      </div>
      {kind === 'login' && (
        <div className='space-y-3 text-center text-sm'>
          <ChipLink
            href={`/auth/forgot-password?next_path=${encodeURIComponent(nextPath)}`}
            prefetch={false}
            className='px-1 text-[var(--text-primary)]'
          >
            忘记密码？
          </ChipLink>
          {!registrationDisabled && (
            <div className='flex items-center justify-center gap-2'>
              <span className='text-[var(--text-muted)]'>还没有账户？</span>
              <ChipLink
                href={`/signup?callbackUrl=${encodeURIComponent(nextPath)}`}
                className='px-1 text-[var(--text-primary)]'
              >
                注册
              </ChipLink>
            </div>
          )}
        </div>
      )}
      {kind === 'register' && (
        <div className='flex items-center justify-center gap-2 text-sm'>
          <span className='text-[var(--text-muted)]'>已有账户？</span>
          <ChipLink href={`/login?callbackUrl=${encodeURIComponent(nextPath)}`} className='px-1 text-[var(--text-primary)]'>
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
