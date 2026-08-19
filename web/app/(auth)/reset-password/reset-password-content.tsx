'use client'

import { Suspense, useState } from 'react'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/lib/utils/errors'
import { useRouter, useSearchParams } from 'next/navigation'
import { identityApi } from '@/lib/auth/identity-api'
import { AuthHeader, AuthNavPrompt } from '@/app/(auth)/components'
import { SetNewPasswordForm } from '@/app/(auth)/reset-password/reset-password-form'

const logger = createLogger('ResetPasswordPage')

function ResetPasswordContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get('token')

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [statusMessage, setStatusMessage] = useState<{
    type: 'success' | 'error' | null
    text: string
  }>({
    type: null,
    text: '',
  })

  const tokenError = !token ? '重置令牌无效或缺失，请重新申请密码重置链接。' : null

  const handleResetPassword = async (password: string) => {
    if (!token) return
    try {
      setIsSubmitting(true)
      setStatusMessage({ type: null, text: '' })

      await identityApi.resetPassword(token, password)

      setStatusMessage({
        type: 'success',
        text: '密码重置成功，正在跳转到登录页面…',
      })

      setTimeout(() => {
        router.push('/login?resetSuccess=true')
      }, 1500)
    } catch (error) {
      logger.error('重置密码失败:', { error })
      setStatusMessage({
        type: 'error',
        text: getErrorMessage(error, '重置密码失败'),
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className='space-y-6'>
      <AuthHeader title='重置密码' description='为你的账户设置新密码' />

      <SetNewPasswordForm
        token={token}
        onSubmit={handleResetPassword}
        isSubmitting={isSubmitting}
        statusType={tokenError ? 'error' : statusMessage.type}
        statusMessage={tokenError ?? statusMessage.text}
      />

      <AuthNavPrompt href='/login' linkLabel='返回登录' />
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={<div className='flex min-h-[320px] items-center justify-center'>加载中…</div>}
    >
      <ResetPasswordContent />
    </Suspense>
  )
}
