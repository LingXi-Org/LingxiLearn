'use client'

import { useState } from 'react'
import { cn } from '@sim/emcn'
import {
  AuthField,
  AuthFormMessage,
  AuthSubmitButton,
  PasswordInput,
} from '@/app/(auth)/components'

interface SetNewPasswordFormProps {
  token: string | null
  onSubmit: (password: string) => Promise<void>
  isSubmitting: boolean
  statusType: 'success' | 'error' | null
  statusMessage: string
  className?: string
}

export function SetNewPasswordForm({
  token,
  onSubmit,
  isSubmitting,
  statusType,
  statusMessage,
  className,
}: SetNewPasswordFormProps) {
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [validationMessages, setValidationMessages] = useState<string[]>([])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const errors: string[] = []

    if (password.length < 8) {
      errors.push('密码至少需要 8 个字符')
    }

    if (password.length > 100) {
      errors.push('密码不能超过 100 个字符')
    }

    if (!/[A-Z]/.test(password)) {
      errors.push('密码至少需要包含一个大写字母')
    }

    if (!/[a-z]/.test(password)) {
      errors.push('密码至少需要包含一个小写字母')
    }

    if (!/[0-9]/.test(password)) {
      errors.push('密码至少需要包含一个数字')
    }

    if (!/[^A-Za-z0-9]/.test(password)) {
      errors.push('密码至少需要包含一个特殊字符')
    }

    if (password !== confirmPassword) {
      errors.push('两次输入的密码不一致')
    }

    if (errors.length > 0) {
      setValidationMessages(errors)
      return
    }

    setValidationMessages([])
    onSubmit(password)
  }

  const hasValidationErrors = validationMessages.length > 0

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
      <div className='space-y-5'>
        <AuthField htmlFor='password' label='新密码'>
          <PasswordInput
            id='password'
            autoCapitalize='none'
            autoComplete='new-password'
            autoCorrect='off'
            disabled={isSubmitting || !token}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            placeholder='请输入新密码'
            error={hasValidationErrors}
          />
        </AuthField>
        <AuthField htmlFor='confirmPassword' label='确认密码'>
          <PasswordInput
            id='confirmPassword'
            autoCapitalize='none'
            autoComplete='new-password'
            autoCorrect='off'
            disabled={isSubmitting || !token}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            placeholder='请再次输入新密码'
            error={hasValidationErrors}
          />
        </AuthField>

        {hasValidationErrors && (
          <AuthFormMessage type='error'>
            {validationMessages.map((error) => (
              <p key={error}>{error}</p>
            ))}
          </AuthFormMessage>
        )}

        {statusType && statusMessage && (
          <AuthFormMessage type={statusType === 'success' ? 'success' : 'error'}>
            <p>{statusMessage}</p>
          </AuthFormMessage>
        )}
      </div>

      <AuthSubmitButton
        loading={isSubmitting}
        loadingLabel='重置中…'
        disabled={!token || password.length === 0 || confirmPassword.length === 0}
      >
        重置密码
      </AuthSubmitButton>
    </form>
  )
}
