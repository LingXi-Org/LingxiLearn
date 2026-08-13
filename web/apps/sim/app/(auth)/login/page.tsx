'use client'

import { useState } from 'react'
import { Button, Input } from '@sim/emcn'
import { useLingxiIdentity } from '@/lib/lingxi/lingxi-identity-provider'

export default function LoginPage() {
  const { client, configured, error: callbackError } = useLingxiIdentity()
  const [message, setMessage] = useState<string | null>(callbackError)
  const [loading, setLoading] = useState(false)

  async function startLogin() {
    if (!client) {
      setMessage(configured ? '登录服务正在初始化，请稍后重试。' : '未配置 Lingxi 身份服务。')
      return
    }
    setLoading(true)
    setMessage(null)
    try {
      await client.login()
    } catch (cause) {
      setLoading(false)
      setMessage(cause instanceof Error ? cause.message : '无法打开登录服务。')
    }
  }

  return (
    <div className='space-y-8'>
      <div className='space-y-2 text-center'>
        <h1 className='text-[32px] leading-[1.2] text-[var(--text-primary)]'>登录灵犀智学</h1>
        <p className='text-base leading-[1.5] text-[var(--text-muted)]'>进入你的智能学习工作台</p>
      </div>
      <div className='space-y-5'>
        <label className='block space-y-2'>
          <span className='text-[13px] text-[var(--text-secondary)]'>账号</span>
          <Input disabled placeholder='由统一身份服务管理' />
        </label>
        <Button className='h-10 w-full' variant='primary' onClick={() => void startLogin()} disabled={loading}>
          {loading ? '正在跳转…' : '使用统一身份服务登录'}
        </Button>
        {message && (
          <p className='text-center text-[13px] leading-5 text-[var(--text-error)]' role='alert'>
            {message}
          </p>
        )}
        <p className='text-center text-[12px] leading-5 text-[var(--text-muted)]'>
          登录后，LingxiGraph 将继续使用你的身份访问学习任务、流式消息和学习资源。
        </p>
      </div>
    </div>
  )
}
