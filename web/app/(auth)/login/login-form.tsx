'use client'

import { useEffect, useRef, useState } from 'react'
import {
  ChipModal,
  ChipModalBody,
  ChipModalError,
  ChipModalField,
  ChipModalFooter,
  ChipModalHeader,
} from '@sim/emcn'
import { createLogger } from '@sim/logger'
import { getErrorMessage } from '@sim/utils/errors'
import { normalizeEmail } from '@sim/utils/string'
import { useRouter, useSearchParams } from 'next/navigation'
import { client } from '@/lib/auth/auth-client'
import { identityApi } from '@/lib/auth/identity-api'
import { getEnv, isFalsy } from '@/lib/core/config/env'
import { isSsoEnabled } from '@/lib/core/config/env-flags'
import { validateCallbackUrl } from '@/lib/core/security/input-validation'
import { getBaseUrl } from '@/lib/core/utils/urls'
import { quickValidateEmail } from '@/lib/messaging/email/validation'
import { captureClientEvent } from '@/lib/posthog/client'
import { buildAuthCrossLink } from '@/app/(auth)/auth-redirect'
import {
  AuthDivider,
  AuthField,
  AuthFormMessage,
  AuthHeader,
  AuthInput,
  AuthLegalFooter,
  AuthNavPrompt,
  AuthSubmitButton,
  AuthTextLink,
  PasswordInput,
  SocialLoginButtons,
  SSOLoginButton,
} from '@/app/(auth)/components'

const logger = createLogger('LoginForm')

const validateEmailField = (emailValue: string): string[] => {
  const errors: string[] = []

  if (!emailValue || !emailValue.trim()) {
    errors.push('请输入邮箱地址。')
    return errors
  }

  const validation = quickValidateEmail(normalizeEmail(emailValue))
  if (!validation.isValid) {
    errors.push(validation.reason || '请输入有效的邮箱地址。')
  }

  return errors
}

const PASSWORD_VALIDATIONS = {
  required: {
    test: (value: string) => Boolean(value && typeof value === 'string'),
    message: '请输入密码。',
  },
  notEmpty: {
    test: (value: string) => value.trim().length > 0,
    message: '密码不能为空。',
  },
}

const validatePassword = (passwordValue: string): string[] => {
  const errors: string[] = []

  if (!PASSWORD_VALIDATIONS.required.test(passwordValue)) {
    errors.push(PASSWORD_VALIDATIONS.required.message)
    return errors
  }

  if (!PASSWORD_VALIDATIONS.notEmpty.test(passwordValue)) {
    errors.push(PASSWORD_VALIDATIONS.notEmpty.message)
    return errors
  }

  return errors
}

export default function LoginPage({
  githubAvailable,
  googleAvailable,
  microsoftAvailable,
  isProduction,
  registrationDisabled,
}: {
  githubAvailable: boolean
  googleAvailable: boolean
  microsoftAvailable: boolean
  isProduction: boolean
  /** DISABLE_REGISTRATION. Hides the signup cross-link, which `/signup` blocks. */
  registrationDisabled: boolean
}) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [isLoading, setIsLoading] = useState(false)
  const [password, setPassword] = useState('')
  const [passwordErrors, setPasswordErrors] = useState<string[]>([])
  const [showValidationError, setShowValidationError] = useState(false)
  const callbackUrlParam = searchParams?.get('callbackUrl')
  const isValidCallbackUrl = callbackUrlParam ? validateCallbackUrl(callbackUrlParam) : false
  const invalidCallbackRef = useRef(false)
  if (callbackUrlParam && !isValidCallbackUrl && !invalidCallbackRef.current) {
    invalidCallbackRef.current = true
    logger.warn('Invalid callback URL detected and blocked:', { url: callbackUrlParam })
  }
  const callbackUrl = isValidCallbackUrl ? callbackUrlParam! : '/workspace/lingxi/home/'
  const isInviteFlow = searchParams?.get('invite_flow') === 'true'
  const signupHref = buildAuthCrossLink('/signup', {
    callbackUrl: isValidCallbackUrl ? callbackUrl : null,
    isInviteFlow,
  })

  const [forgotPasswordOpen, setForgotPasswordOpen] = useState(false)
  const [forgotPasswordEmail, setForgotPasswordEmail] = useState('')
  const [isSubmittingReset, setIsSubmittingReset] = useState(false)
  const [resetStatus, setResetStatus] = useState<{
    type: 'success' | 'error' | null
    message: string
  }>({ type: null, message: '' })

  const [email, setEmail] = useState('')
  const [emailErrors, setEmailErrors] = useState<string[]>([])
  const [showEmailValidationError, setShowEmailValidationError] = useState(false)
  const [resetSuccessMessage, setResetSuccessMessage] = useState<string | null>(() =>
    searchParams?.get('resetSuccess') === 'true' ? '密码重置成功，请使用新密码登录。' : null
  )

  useEffect(() => {
    captureClientEvent('login_page_viewed', {})
  }, [])

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newEmail = e.target.value
    setEmail(newEmail)

    const errors = validateEmailField(newEmail)
    setEmailErrors(errors)
    setShowEmailValidationError(false)
  }

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newPassword = e.target.value
    setPassword(newPassword)

    const errors = validatePassword(newPassword)
    setPasswordErrors(errors)
    setShowValidationError(false)
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setIsLoading(true)

    const redirectToVerify = (emailToVerify: string) => {
      if (typeof window !== 'undefined') {
        sessionStorage.setItem('verificationEmail', emailToVerify)
      }
      router.push('/verify')
    }

    const formData = new FormData(e.currentTarget)
    const emailRaw = formData.get('email') as string
    const email = normalizeEmail(emailRaw)

    const emailValidationErrors = validateEmailField(email)
    setEmailErrors(emailValidationErrors)
    setShowEmailValidationError(emailValidationErrors.length > 0)

    const passwordValidationErrors = validatePassword(password)
    setPasswordErrors(passwordValidationErrors)
    setShowValidationError(passwordValidationErrors.length > 0)

    if (emailValidationErrors.length > 0 || passwordValidationErrors.length > 0) {
      setIsLoading(false)
      return
    }

    try {
      const safeCallbackUrl = callbackUrl
      let errorHandled = false

      const result = await client.signIn.email(
        {
          email,
          password,
          callbackURL: safeCallbackUrl,
        },
        {
          onError: (ctx: any) => {
            logger.error('Login error:', ctx.error)

            if (ctx.error.code?.includes('EMAIL_NOT_VERIFIED')) {
              errorHandled = true
              redirectToVerify(email)
              return
            }

            errorHandled = true
            const errorMessage: string[] = ['邮箱或密码错误']

            if (
              ctx.error.code?.includes('BAD_REQUEST') ||
              ctx.error.message?.includes('Email and password sign in is not enabled')
            ) {
              errorMessage.push('当前已禁用邮箱密码登录。')
            } else if (
              ctx.error.code?.includes('INVALID_CREDENTIALS') ||
              ctx.error.message?.includes('invalid password')
            ) {
              errorMessage.push('邮箱或密码错误，请重试。')
            } else if (
              ctx.error.code?.includes('USER_NOT_FOUND') ||
              ctx.error.message?.includes('not found')
            ) {
              errorMessage.push('未找到该邮箱对应的账户，请先注册。')
            } else if (ctx.error.code?.includes('MISSING_CREDENTIALS')) {
              errorMessage.push('请输入邮箱和密码。')
            } else if (ctx.error.code?.includes('EMAIL_PASSWORD_DISABLED')) {
              errorMessage.push('邮箱密码登录已被禁用。')
            } else if (ctx.error.code?.includes('FAILED_TO_CREATE_SESSION')) {
              errorMessage.push('创建会话失败，请稍后重试。')
            } else if (ctx.error.code?.includes('too many attempts')) {
              errorMessage.push('登录尝试次数过多，请稍后重试或重置密码。')
            } else if (ctx.error.code?.includes('account locked')) {
              errorMessage.push('出于安全原因，你的账户已锁定，请重置密码。')
            } else if (ctx.error.code?.includes('network')) {
              errorMessage.push('网络错误，请检查网络连接后重试。')
            } else if (ctx.error.message?.includes('rate limit')) {
              errorMessage.push('请求过于频繁，请稍后重试。')
            }

            setResetSuccessMessage(null)
            setPasswordErrors(errorMessage)
            setShowValidationError(true)
          },
        }
      )

      // The production identity flow has already started a full-page
      // navigation. Do not let the success fallback below overwrite it with
      // an immediate client-side route change.
      if (result?.redirectStarted) return

      if (!result || result.error) {
        // Show error if not already handled by onError callback
        if (!errorHandled) {
          setResetSuccessMessage(null)
          const errorMessage = result?.error?.message || '登录失败，请重试。'
          setPasswordErrors([errorMessage])
          setShowValidationError(true)
        }
        setIsLoading(false)
        return
      }

      // Clear reset success message on successful login
      setResetSuccessMessage(null)

      // Explicit redirect fallback if better-auth doesn't redirect
      router.push(safeCallbackUrl)
    } catch (err: any) {
      if (err.message?.includes('not verified') || err.code?.includes('EMAIL_NOT_VERIFIED')) {
        redirectToVerify(email)
        return
      }

      logger.error('Uncaught login error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleForgotPassword = async () => {
    if (!forgotPasswordEmail) {
      setResetStatus({
        type: 'error',
        message: '请输入邮箱地址',
      })
      return
    }

    const emailValidation = quickValidateEmail(normalizeEmail(forgotPasswordEmail))
    if (!emailValidation.isValid) {
      setResetStatus({
        type: 'error',
        message: '请输入有效的邮箱地址',
      })
      return
    }

    try {
      setIsSubmittingReset(true)
      setResetStatus({ type: null, message: '' })

      try {
        await identityApi.requestPasswordReset(
          forgotPasswordEmail,
          `${getBaseUrl()}/reset-password`
        )
      } catch (requestError) {
        let errorMessage = getErrorMessage(requestError, '申请重置密码失败')

        if (
          errorMessage.includes('Invalid body parameters') ||
          errorMessage.includes('invalid email')
        ) {
          errorMessage = '请输入有效的邮箱地址'
        } else if (errorMessage.includes('Email is required')) {
          errorMessage = '请输入邮箱地址'
        } else if (
          errorMessage.includes('user not found') ||
          errorMessage.includes('User not found')
        ) {
          errorMessage = '未找到该邮箱对应的账户'
        }

        throw new Error(errorMessage)
      }

      setResetStatus({
        type: 'success',
        message: '密码重置链接已发送到你的邮箱',
      })

      setTimeout(() => {
        setForgotPasswordOpen(false)
        setResetStatus({ type: null, message: '' })
      }, 2000)
    } catch (error) {
      logger.error('Error requesting password reset:', { error })
      setResetStatus({
        type: 'error',
        message: getErrorMessage(error, '申请重置密码失败'),
      })
    } finally {
      setIsSubmittingReset(false)
    }
  }

  const ssoEnabled = isSsoEnabled
  const emailEnabled = !isFalsy(getEnv('NEXT_PUBLIC_EMAIL_PASSWORD_SIGNUP_ENABLED'))
  const hasSocial = githubAvailable || googleAvailable || microsoftAvailable
  const hasOnlySSO = ssoEnabled && !emailEnabled && !hasSocial
  const showTopSSO = hasOnlySSO
  const showBottomSection = hasSocial || (ssoEnabled && !hasOnlySSO)
  const showDivider = (emailEnabled || showTopSSO) && showBottomSection

  const emailFieldErrors = showEmailValidationError && emailErrors.length > 0 ? emailErrors : []
  const passwordFieldErrors = showValidationError && passwordErrors.length > 0 ? passwordErrors : []
  const canSubmit = email.trim().length > 0 && password.length > 0

  return (
    <>
      <div className='space-y-6'>
        <AuthHeader title='登录' description='使用你的账户继续' />

        {showTopSSO && <SSOLoginButton callbackURL={callbackUrl} variant='primary' />}

        {emailEnabled && (
          <form onSubmit={onSubmit} className='space-y-6'>
            <div className='space-y-5'>
              <AuthField htmlFor='email' label='邮箱' errors={emailFieldErrors}>
                <AuthInput
                  id='email'
                  name='email'
                  placeholder='请输入邮箱地址'
                  required
                  autoCapitalize='none'
                  autoComplete='email'
                  autoCorrect='off'
                  value={email}
                  onChange={handleEmailChange}
                  error={emailFieldErrors.length > 0}
                />
              </AuthField>
              <AuthField
                htmlFor='password'
                label='密码'
                errors={passwordFieldErrors}
                action={
                  <AuthTextLink
                    onClick={() => setForgotPasswordOpen(true)}
                    className='text-caption'
                  >
                    忘记密码？
                  </AuthTextLink>
                }
              >
                <PasswordInput
                  id='password'
                  name='password'
                  required
                  autoCapitalize='none'
                  autoComplete='current-password'
                  autoCorrect='off'
                  placeholder='请输入密码'
                  value={password}
                  onChange={handlePasswordChange}
                  error={passwordFieldErrors.length > 0}
                />
              </AuthField>
            </div>

            {resetSuccessMessage && (
              <AuthFormMessage type='success'>
                <p>{resetSuccessMessage}</p>
              </AuthFormMessage>
            )}

            <AuthSubmitButton loading={isLoading} loadingLabel='登录中…' disabled={!canSubmit}>
              登录
            </AuthSubmitButton>
          </form>
        )}

        {showDivider && <AuthDivider label='或使用以下方式继续' />}

        {showBottomSection && (
          <SocialLoginButtons
            googleAvailable={googleAvailable}
            githubAvailable={githubAvailable}
            microsoftAvailable={microsoftAvailable}
            isProduction={isProduction}
            callbackURL={callbackUrl}
          >
            {ssoEnabled && !hasOnlySSO && (
              <SSOLoginButton callbackURL={callbackUrl} variant='outline' />
            )}
          </SocialLoginButtons>
        )}

        {emailEnabled && !registrationDisabled && (
          <AuthNavPrompt prompt='还没有账户？' href={signupHref} linkLabel='注册' />
        )}

        <AuthLegalFooter action='登录' />
      </div>

      <ChipModal open={forgotPasswordOpen} onOpenChange={setForgotPasswordOpen} srTitle='重置密码'>
        <ChipModalHeader onClose={() => setForgotPasswordOpen(false)}>重置密码</ChipModalHeader>
        <ChipModalBody>
          <p className='px-2 text-[var(--text-secondary)] text-sm'>
            输入邮箱地址后，如果账户存在，我们会向你发送密码重置链接。
          </p>
          <ChipModalField
            type='email'
            title='邮箱'
            value={forgotPasswordEmail}
            onChange={(value) => setForgotPasswordEmail(value)}
            onSubmit={() => {
              if (!isSubmittingReset) void handleForgotPassword()
            }}
            required
            placeholder='you@example.com'
          />
          {resetStatus.type === 'success' && (
            <p className='px-2 text-[var(--text-secondary)] text-sm'>{resetStatus.message}</p>
          )}
          <ChipModalError>
            {resetStatus.type === 'error' ? resetStatus.message : null}
          </ChipModalError>
        </ChipModalBody>
        <ChipModalFooter
          onCancel={() => setForgotPasswordOpen(false)}
          cancelDisabled={isSubmittingReset}
          primaryAction={{
            label: isSubmittingReset ? '发送中…' : '发送重置链接',
            onClick: handleForgotPassword,
            disabled: !forgotPasswordEmail || isSubmittingReset,
          }}
        />
      </ChipModal>
    </>
  )
}
