'use client'

import { useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { identityApi } from '@/lib/auth/identity-api'
import { validateCallbackUrl } from '@/lib/core/security/input-validation'
import {
  AuthField,
  AuthHeader,
  AuthInput,
  AuthLegalFooter,
  AuthNavPrompt,
  AuthSubmitButton,
} from '@/app/(auth)/components'

export function SSOForm({ registrationDisabled }: { registrationDisabled: boolean }) {
  const searchParams = useSearchParams()
  const [email, setEmail] = useState(searchParams.get('email') ?? '')
  const [isLoading, setIsLoading] = useState(false)
  const callbackParam = searchParams.get('callbackUrl')
  const callbackUrl =
    callbackParam && validateCallbackUrl(callbackParam) ? callbackParam : '/workspace/lingxi/home/'

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!email.trim()) return
    setIsLoading(true)
    window.location.assign(
      `${identityApi.authUrl('sso', callbackUrl)}&email=${encodeURIComponent(email.trim())}`
    )
  }

  return (
    <div className='space-y-6'>
      <AuthHeader title='使用单点登录' description='输入工作邮箱以继续' />
      <form onSubmit={onSubmit} className='space-y-6'>
        <AuthField htmlFor='email' label='工作邮箱'>
          <AuthInput
            id='email'
            name='email'
            type='email'
            placeholder='请输入工作邮箱'
            autoComplete='email'
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </AuthField>
        <AuthSubmitButton loading={isLoading} loadingLabel='正在跳转…' disabled={!email.trim()}>
          使用单点登录继续
        </AuthSubmitButton>
      </form>
      <AuthNavPrompt
        href={`/login?callbackUrl=${encodeURIComponent(callbackUrl)}`}
        linkLabel='返回邮箱登录'
      />
      {!registrationDisabled && (
        <AuthNavPrompt
          prompt='还没有账户？'
          href={`/signup?callbackUrl=${encodeURIComponent(callbackUrl)}`}
          linkLabel='注册'
        />
      )}
      <AuthLegalFooter action='登录' />
    </div>
  )
}
