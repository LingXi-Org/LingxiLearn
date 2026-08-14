'use client'

import { Suspense, useEffect, useRef, useState } from 'react'
import { Turnstile, type TurnstileInstance } from '@marsidev/react-turnstile'
import { createLogger } from '@sim/logger'
import { useRouter, useSearchParams } from 'next/navigation'
import { usePostHog } from 'posthog-js/react'
import { client, useSession } from '@/lib/auth/auth-client'
import { getEnv, isFalsy } from '@/lib/core/config/env'
import { isSsoEnabled } from '@/lib/core/config/env-flags'
import { validateCallbackUrl } from '@/lib/core/security/input-validation'
import { quickValidateEmail } from '@/lib/messaging/email/validation'
import { captureClientEvent, captureEvent } from '@/lib/posthog/client'
import {
  buildAuthCrossLink,
  DEFAULT_POST_AUTH_ROUTE,
  POST_AUTH_REDIRECT_STORAGE_KEY,
  resolveAuthRedirect,
  resolvePostSignupDestination,
  VERIFY_FROM_SIGNUP_ROUTE,
} from '@/app/(auth)/auth-redirect'
import {
  AuthDivider,
  AuthField,
  AuthFormMessage,
  AuthHeader,
  AuthInput,
  AuthLegalFooter,
  AuthNavPrompt,
  AuthSubmitButton,
  PasswordInput,
  SocialLoginButtons,
  SSOLoginButton,
} from '@/app/(auth)/components'

const logger = createLogger('SignupForm')

const PASSWORD_VALIDATIONS = {
  minLength: { regex: /.{8,}/, message: '密码至少需要 8 个字符。' },
  uppercase: {
    regex: /(?=.*?[A-Z])/,
    message: '密码至少需要包含一个大写字母。',
  },
  lowercase: {
    regex: /(?=.*?[a-z])/,
    message: '密码至少需要包含一个小写字母。',
  },
  number: { regex: /(?=.*?[0-9])/, message: '密码至少需要包含一个数字。' },
  special: {
    regex: /(?=.*?[#?!@$%^&*-])/,
    message: '密码至少需要包含一个特殊字符。',
  },
}

const NAME_VALIDATIONS = {
  required: {
    test: (value: string) => Boolean(value && typeof value === 'string'),
    message: '请输入姓名。',
  },
  notEmpty: {
    test: (value: string) => value.trim().length > 0,
    message: '姓名不能为空。',
  },
  validCharacters: {
    regex: /^[\p{L}\s\-']+$/u,
    message: '姓名只能包含文字、空格、连字符和撇号。',
  },
  noConsecutiveSpaces: {
    regex: /^(?!.*\s\s).*$/,
    message: '姓名不能包含连续空格。',
  },
}

const validateEmailField = (emailValue: string): string[] => {
  const errors: string[] = []

  if (!emailValue || !emailValue.trim()) {
    errors.push('请输入邮箱地址。')
    return errors
  }

  const validation = quickValidateEmail(emailValue.trim().toLowerCase())
  if (!validation.isValid) {
    errors.push(validation.reason || '请输入有效的邮箱地址。')
  }

  return errors
}

interface SignupFormProps {
  githubAvailable: boolean
  googleAvailable: boolean
  microsoftAvailable: boolean
  isProduction: boolean
  emailSignupEnabled: boolean
  /** Server-derived: verification is enabled AND a mail provider is configured. */
  emailVerificationEnabled: boolean
}

function SignupFormContent({
  githubAvailable,
  googleAvailable,
  microsoftAvailable,
  isProduction,
  emailSignupEnabled,
  emailVerificationEnabled,
}: SignupFormProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { refetch: refetchSession } = useSession()
  const posthog = usePostHog()
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    captureClientEvent('signup_page_viewed', {})
  }, [])
  const [password, setPassword] = useState('')
  const [passwordErrors, setPasswordErrors] = useState<string[]>([])
  const [showValidationError, setShowValidationError] = useState(false)
  const [email, setEmail] = useState(() => searchParams.get('email') ?? '')
  const [emailError, setEmailError] = useState('')
  const [emailErrors, setEmailErrors] = useState<string[]>([])
  const [showEmailValidationError, setShowEmailValidationError] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const turnstileRef = useRef<TurnstileInstance>(null)
  const [turnstileSiteKey] = useState(() => getEnv('NEXT_PUBLIC_TURNSTILE_SITE_KEY'))
  const { rawCallbackUrl: rawRedirectUrl, isInviteFlow } = resolveAuthRedirect({
    redirect: searchParams.get('redirect'),
    callbackUrl: searchParams.get('callbackUrl'),
    inviteFlow: searchParams.get('invite_flow'),
  })
  const isValidRedirectUrl = rawRedirectUrl ? validateCallbackUrl(rawRedirectUrl) : false
  const invalidCallbackRef = useRef(false)
  if (rawRedirectUrl && !isValidRedirectUrl && !invalidCallbackRef.current) {
    invalidCallbackRef.current = true
    logger.warn('Invalid callback URL detected and blocked:', { url: rawRedirectUrl })
  }
  const redirectUrl = isValidRedirectUrl ? rawRedirectUrl : ''

  const [name, setName] = useState('')
  const [nameErrors, setNameErrors] = useState<string[]>([])
  const [showNameValidationError, setShowNameValidationError] = useState(false)

  const validatePassword = (passwordValue: string): string[] => {
    const errors: string[] = []

    if (!PASSWORD_VALIDATIONS.minLength.regex.test(passwordValue)) {
      errors.push(PASSWORD_VALIDATIONS.minLength.message)
    }

    if (!PASSWORD_VALIDATIONS.uppercase.regex.test(passwordValue)) {
      errors.push(PASSWORD_VALIDATIONS.uppercase.message)
    }

    if (!PASSWORD_VALIDATIONS.lowercase.regex.test(passwordValue)) {
      errors.push(PASSWORD_VALIDATIONS.lowercase.message)
    }

    if (!PASSWORD_VALIDATIONS.number.regex.test(passwordValue)) {
      errors.push(PASSWORD_VALIDATIONS.number.message)
    }

    if (!PASSWORD_VALIDATIONS.special.regex.test(passwordValue)) {
      errors.push(PASSWORD_VALIDATIONS.special.message)
    }

    return errors
  }

  const validateName = (nameValue: string): string[] => {
    const errors: string[] = []

    if (!NAME_VALIDATIONS.required.test(nameValue)) {
      errors.push(NAME_VALIDATIONS.required.message)
      return errors
    }

    if (!NAME_VALIDATIONS.notEmpty.test(nameValue)) {
      errors.push(NAME_VALIDATIONS.notEmpty.message)
      return errors
    }

    if (!NAME_VALIDATIONS.validCharacters.regex.test(nameValue.trim())) {
      errors.push(NAME_VALIDATIONS.validCharacters.message)
    }

    if (!NAME_VALIDATIONS.noConsecutiveSpaces.regex.test(nameValue)) {
      errors.push(NAME_VALIDATIONS.noConsecutiveSpaces.message)
    }

    return errors
  }

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newPassword = e.target.value
    setPassword(newPassword)

    const errors = validatePassword(newPassword)
    setPasswordErrors(errors)
    setShowValidationError(false)
  }

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const rawValue = e.target.value
    setName(rawValue)

    const errors = validateName(rawValue)
    setNameErrors(errors)
    setShowNameValidationError(false)
  }

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newEmail = e.target.value
    setEmail(newEmail)

    const errors = validateEmailField(newEmail)
    setEmailErrors(errors)
    setShowEmailValidationError(false)

    if (emailError) {
      setEmailError('')
    }
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setIsLoading(true)

    const formData = new FormData(e.currentTarget)
    const emailValueRaw = formData.get('email') as string
    const emailValue = emailValueRaw.trim().toLowerCase()
    const passwordValue = formData.get('password') as string
    const nameValue = formData.get('name') as string

    const trimmedName = nameValue.trim()

    const nameValidationErrors = validateName(trimmedName)
    setNameErrors(nameValidationErrors)
    setShowNameValidationError(nameValidationErrors.length > 0)

    const emailValidationErrors = validateEmailField(emailValue)
    setEmailErrors(emailValidationErrors)
    setShowEmailValidationError(emailValidationErrors.length > 0)

    const errors = validatePassword(passwordValue)
    setPasswordErrors(errors)

    setShowValidationError(errors.length > 0)

    try {
      if (
        nameValidationErrors.length > 0 ||
        emailValidationErrors.length > 0 ||
        errors.length > 0
      ) {
        setIsLoading(false)
        return
      }

      if (trimmedName.length > 100) {
        setNameErrors(['姓名最多只能包含 100 个字符，请缩短姓名。'])
        setShowNameValidationError(true)
        setIsLoading(false)
        return
      }

      let token: string | undefined
      const widget = turnstileRef.current
      if (turnstileSiteKey && widget) {
        try {
          widget.reset()
          widget.execute()
          token = await widget.getResponsePromise()
        } catch {
          captureEvent(posthog, 'signup_failed', {
            error_code: 'captcha_client_failure',
          })
          setFormError('验证码校验失败，请重试。')
          setIsLoading(false)
          return
        }
      }

      setFormError(null)
      const response = await client.signUp.email(
        {
          email: emailValue,
          password: passwordValue,
          name: trimmedName,
        },
        {
          headers: {
            ...(token ? { 'x-captcha-response': token } : {}),
          },
          onError: (ctx) => {
            logger.warn('Signup error:', ctx.error)
            const errorMessage: string[] = ['创建账户失败']

            let errorCode = 'unknown'
            if (ctx.error.code?.includes('USER_ALREADY_EXISTS')) {
              errorCode = 'user_already_exists'
              setEmailError('该邮箱已注册账户，请直接登录。')
            } else if (
              ctx.error.code?.includes('BAD_REQUEST') ||
              ctx.error.message?.includes('Email and password sign up is not enabled')
            ) {
              errorCode = 'signup_disabled'
              errorMessage.push('当前已禁用邮箱注册。')
              setEmailError(errorMessage[0])
            } else if (ctx.error.code?.includes('INVALID_EMAIL')) {
              errorCode = 'invalid_email'
              errorMessage.push('请输入有效的邮箱地址。')
              setEmailError(errorMessage[0])
            } else if (ctx.error.code?.includes('PASSWORD_TOO_SHORT')) {
              errorCode = 'password_too_short'
              errorMessage.push('密码至少需要 8 个字符。')
              setPasswordErrors(errorMessage)
              setShowValidationError(true)
            } else if (ctx.error.code?.includes('PASSWORD_TOO_LONG')) {
              errorCode = 'password_too_long'
              errorMessage.push('密码不能超过 128 个字符。')
              setPasswordErrors(errorMessage)
              setShowValidationError(true)
            } else if (ctx.error.code?.includes('network')) {
              errorCode = 'network_error'
              errorMessage.push('网络错误，请检查网络连接后重试。')
              setPasswordErrors(errorMessage)
              setShowValidationError(true)
            } else if (ctx.error.code?.includes('rate limit')) {
              errorCode = 'rate_limited'
              errorMessage.push('请求过于频繁，请稍后重试。')
              setPasswordErrors(errorMessage)
              setShowValidationError(true)
            } else {
              setPasswordErrors(errorMessage)
              setShowValidationError(true)
            }

            captureEvent(posthog, 'signup_failed', { error_code: errorCode })
          },
        }
      )

      // The identity BFF owns the browser navigation in production. Waiting
      // for a session here would race that navigation and can send the user
      // back to the pre-auth route.
      if (response?.redirectStarted) return

      if (!response || response.error) {
        setIsLoading(false)
        return
      }

      try {
        await refetchSession()
        logger.info('Session refreshed after successful signup')
      } catch (sessionError) {
        logger.error('Failed to refresh session after signup:', sessionError)
      }

      const destination = resolvePostSignupDestination({ emailVerificationEnabled, redirectUrl })

      if (typeof window !== 'undefined') {
        // Clear any leftover from an earlier signup in this tab — otherwise a
        // signup with no callbackUrl inherits the previous CLI/invite destination.
        sessionStorage.removeItem('verificationEmail')
        sessionStorage.removeItem(POST_AUTH_REDIRECT_STORAGE_KEY)

        if (destination.kind === 'verify') {
          sessionStorage.setItem('verificationEmail', emailValue)
          if (redirectUrl) sessionStorage.setItem(POST_AUTH_REDIRECT_STORAGE_KEY, redirectUrl)
        }
      }

      if (destination.kind === 'verify') {
        router.push(VERIFY_FROM_SIGNUP_ROUTE)
      } else if (destination.kind === 'redirect') {
        // Full navigation, matching the verify hop: the destination (invite, CLI
        // handoff) is server-rendered and must see the fresh session cookie.
        window.location.href = destination.url
      } else {
        router.push(DEFAULT_POST_AUTH_ROUTE)
      }
    } catch (error) {
      logger.error('Signup error:', error)
      setIsLoading(false)
    }
  }

  const ssoEnabled = isSsoEnabled
  const emailEnabled =
    !isFalsy(getEnv('NEXT_PUBLIC_EMAIL_PASSWORD_SIGNUP_ENABLED')) && emailSignupEnabled
  const hasSocial = githubAvailable || googleAvailable || microsoftAvailable
  const hasOnlySSO = ssoEnabled && !emailEnabled && !hasSocial
  const showBottomSection = hasSocial || (ssoEnabled && !hasOnlySSO)
  const showDivider = (emailEnabled || hasOnlySSO) && showBottomSection

  const nameFieldErrors = showNameValidationError && nameErrors.length > 0 ? nameErrors : []
  const emailHasError = Boolean(emailError) || (showEmailValidationError && emailErrors.length > 0)
  const emailFieldErrors =
    showEmailValidationError && emailErrors.length > 0
      ? emailErrors
      : emailError && !showEmailValidationError
        ? [emailError]
        : []
  const passwordFieldErrors = showValidationError && passwordErrors.length > 0 ? passwordErrors : []
  const canSubmit = name.trim().length > 0 && email.trim().length > 0 && password.length > 0

  return (
    <div className='space-y-6'>
      <AuthHeader title='创建账户' description='注册灵犀智学账户' />

      {hasOnlySSO && <SSOLoginButton callbackURL={redirectUrl || '/workspace'} variant='primary' />}

      {emailEnabled && (
        <form onSubmit={onSubmit} className='space-y-6'>
          <div className='space-y-5'>
            <AuthField htmlFor='name' label='姓名' errors={nameFieldErrors}>
              <AuthInput
                id='name'
                name='name'
                placeholder='请输入姓名'
                type='text'
                autoCapitalize='words'
                autoComplete='name'
                title='姓名只能包含文字、空格、连字符和撇号'
                value={name}
                onChange={handleNameChange}
                error={nameFieldErrors.length > 0}
              />
            </AuthField>
            <AuthField htmlFor='email' label='邮箱' errors={emailFieldErrors}>
              <AuthInput
                id='email'
                name='email'
                placeholder='请输入邮箱地址'
                autoCapitalize='none'
                autoComplete='email'
                autoCorrect='off'
                value={email}
                onChange={handleEmailChange}
                error={emailHasError}
              />
            </AuthField>
            <AuthField htmlFor='password' label='密码' errors={passwordFieldErrors}>
              <PasswordInput
                id='password'
                name='password'
                autoCapitalize='none'
                autoComplete='new-password'
                placeholder='请输入密码'
                autoCorrect='off'
                value={password}
                onChange={handlePasswordChange}
                error={passwordFieldErrors.length > 0}
              />
            </AuthField>
          </div>

          {turnstileSiteKey && (
            <Turnstile
              ref={turnstileRef}
              siteKey={turnstileSiteKey}
              options={{ execution: 'execute', appearance: 'execute' }}
            />
          )}

          {formError && (
            <AuthFormMessage type='error'>
              <p>{formError}</p>
            </AuthFormMessage>
          )}

          <AuthSubmitButton loading={isLoading} loadingLabel='创建中…' disabled={!canSubmit}>
            创建账户
          </AuthSubmitButton>
        </form>
      )}

      {showDivider && <AuthDivider label='或使用以下方式继续' />}

      {showBottomSection && (
        <SocialLoginButtons
          githubAvailable={githubAvailable}
          googleAvailable={googleAvailable}
          microsoftAvailable={microsoftAvailable}
          callbackURL={redirectUrl || '/workspace'}
          isProduction={isProduction}
        >
          {ssoEnabled && !hasOnlySSO && (
            <SSOLoginButton callbackURL={redirectUrl || '/workspace'} variant='outline' />
          )}
        </SocialLoginButtons>
      )}

      <AuthNavPrompt
        prompt='已有账户？'
        href={buildAuthCrossLink('/login', { callbackUrl: redirectUrl || null, isInviteFlow })}
        linkLabel='登录'
      />

      <AuthLegalFooter action='创建账户' />
    </div>
  )
}

export default function SignupPage({
  githubAvailable,
  googleAvailable,
  microsoftAvailable,
  isProduction,
  emailSignupEnabled,
  emailVerificationEnabled,
}: SignupFormProps) {
  return (
    <Suspense
      fallback={<div className='flex min-h-[320px] items-center justify-center'>加载中…</div>}
    >
      <SignupFormContent
        githubAvailable={githubAvailable}
        googleAvailable={googleAvailable}
        microsoftAvailable={microsoftAvailable}
        isProduction={isProduction}
        emailSignupEnabled={emailSignupEnabled}
        emailVerificationEnabled={emailVerificationEnabled}
      />
    </Suspense>
  )
}
