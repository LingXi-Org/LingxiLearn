'use client'

import { Button } from '@sim/emcn'
import { useLingxiIdentity } from '@/lib/lingxi/lingxi-identity-provider'

export default function AuthCallbackPage() {
  const { ready, authenticated, error } = useLingxiIdentity()

  return (
    <main className='flex min-h-screen items-center justify-center bg-[var(--surface-1)] p-6'>
      <div className='w-full max-w-md rounded-2xl border border-[var(--border-1)] bg-[var(--surface-2)] p-8 text-center shadow-sm'>
        <h1 className='font-medium text-xl text-[var(--text-primary)]'>灵犀智学登录</h1>
        <p className='mt-3 text-sm text-[var(--text-secondary)]'>
          {!ready
            ? '正在处理登录回调…'
            : error
              ? `登录失败：${error}`
              : authenticated
                ? '登录成功，可以进入学习工作台。'
                : '未检测到有效的登录回调。'}
        </p>
        {ready && (
          <Button className='mt-6' onClick={() => window.location.assign('/workspace/lingxi/home')}>
            进入工作台
          </Button>
        )}
      </div>
    </main>
  )
}
