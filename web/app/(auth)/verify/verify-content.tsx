'use client'

import { Suspense, useEffect, useState } from 'react'
import { cn, InputOTP, InputOTPGroup, InputOTPSlot } from '@sim/emcn'
import { POST_AUTH_REDIRECT_STORAGE_KEY } from '@/app/(auth)/auth-redirect'
import {
  AuthFormMessage,
  AuthHeader,
  AuthNavPrompt,
  AuthSubmitButton,
  AuthTextLink,
} from '@/app/(auth)/components'
import { useVerification } from '@/app/(auth)/verify/use-verification'

interface VerifyContentProps {
  hasEmailService: boolean
  isProduction: boolean
  isEmailVerificationEnabled: boolean
}

const OTP_SLOTS = [0, 1, 2, 3, 4, 5] as const

function VerificationForm({
  hasEmailService,
  isProduction,
  isEmailVerificationEnabled,
}: {
  hasEmailService: boolean
  isProduction: boolean
  isEmailVerificationEnabled: boolean
}) {
  const {
    otp,
    email,
    status,
    isResending,
    errorMessage,
    isOtpComplete,
    verifyCode,
    resendCode,
    handleOtpChange,
  } = useVerification({ hasEmailService, isProduction, isEmailVerificationEnabled })

  const isVerified = status === 'verified'
  const isLoading = status === 'verifying' || isResending
  const isInvalidOtp = status === 'error'

  const [countdown, setCountdown] = useState(0)

  useEffect(() => {
    if (countdown <= 0) return
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000)
    return () => clearTimeout(timer)
  }, [countdown])

  const handleResend = () => {
    resendCode()
    setCountdown(30)
  }

  return (
    <div className='space-y-6'>
      <AuthHeader
        title={isVerified ? '邮箱验证成功' : '验证邮箱'}
        description={
          isVerified
            ? '邮箱已验证，正在跳转到工作台…'
            : !isEmailVerificationEnabled
              ? '邮箱验证已关闭，正在跳转到工作台…'
              : hasEmailService
                ? `验证码已发送到 ${email || '你的邮箱'}`
                : !isProduction
                  ? '开发模式：请查看控制台日志获取验证码'
                  : '错误：邮箱验证已开启，但尚未配置邮件服务'
        }
      />

      {!isVerified && isEmailVerificationEnabled && (
        <div className='space-y-6'>
          <div className='space-y-5'>
            <p className='text-center text-[var(--text-muted)] text-sm'>
              请输入 6 位验证码完成账户验证。
              {hasEmailService ? ' 如果收件箱中没有，请检查垃圾邮件文件夹。' : ''}
            </p>

            <div className='flex justify-center'>
              <InputOTP maxLength={6} value={otp} onChange={handleOtpChange} disabled={isLoading}>
                <InputOTPGroup>
                  {OTP_SLOTS.map((index) => (
                    <InputOTPSlot
                      key={index}
                      index={index}
                      className={cn(isInvalidOtp && 'border-[var(--text-error)]')}
                    />
                  ))}
                </InputOTPGroup>
              </InputOTP>
            </div>

            {errorMessage && (
              <AuthFormMessage type='error' align='center'>
                <p>{errorMessage}</p>
              </AuthFormMessage>
            )}
          </div>

          <AuthSubmitButton
            type='button'
            onClick={verifyCode}
            loading={isLoading}
            loadingLabel='验证中…'
            disabled={!isOtpComplete}
          >
            验证邮箱
          </AuthSubmitButton>

          {hasEmailService && (
            <p className='text-center text-[var(--text-muted)] text-sm'>
              没有收到验证码？{' '}
              {countdown > 0 ? (
                <span>请在 {countdown} 秒后重新发送</span>
              ) : (
                <AuthTextLink onClick={handleResend} disabled={isLoading}>
                  重新发送
                </AuthTextLink>
              )}
            </p>
          )}

          <AuthNavPrompt
            href='/signup'
            linkLabel='返回注册'
            onNavigate={() => {
              if (typeof window !== 'undefined') {
                sessionStorage.removeItem('verificationEmail')
                sessionStorage.removeItem(POST_AUTH_REDIRECT_STORAGE_KEY)
              }
            }}
          />
        </div>
      )}
    </div>
  )
}

function VerificationFormFallback() {
  return (
    <div className='text-center'>
      <div className='animate-pulse'>
        <div className='mx-auto mb-4 h-8 w-48 rounded bg-[var(--surface-4)]' />
        <div className='mx-auto h-4 w-64 rounded bg-[var(--surface-4)]' />
      </div>
    </div>
  )
}

export function VerifyContent({
  hasEmailService,
  isProduction,
  isEmailVerificationEnabled,
}: VerifyContentProps) {
  return (
    <Suspense fallback={<VerificationFormFallback />}>
      <VerificationForm
        hasEmailService={hasEmailService}
        isProduction={isProduction}
        isEmailVerificationEnabled={isEmailVerificationEnabled}
      />
    </Suspense>
  )
}
