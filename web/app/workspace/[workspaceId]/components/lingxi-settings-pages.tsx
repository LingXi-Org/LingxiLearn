'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { api } from '@/lib/lingxi/api'

function SettingsShell({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <div className='flex h-full min-h-0 flex-col bg-[var(--bg)]'>
      <header className='shrink-0 border-[var(--border)] border-b px-6 py-4'>
        <h1 className='font-medium text-[15px] text-[var(--text-primary)]'>{title}</h1>
        <p className='mt-1 text-[12px] text-[var(--text-muted)]'>{description}</p>
      </header>
      <main className='min-h-0 flex-1 overflow-y-auto p-6'>
        <div className='mx-auto max-w-[900px]'>{children}</div>
      </main>
    </div>
  )
}

function PlaceholderCard({ title, description }: { title: string; description: string }) {
  return (
    <section className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-5'>
      <h2 className='font-medium text-[14px] text-[var(--text-primary)]'>{title}</h2>
      <p className='mt-2 text-[12px] leading-5 text-[var(--text-muted)]'>{description}</p>
      <span className='mt-4 inline-flex rounded-full border border-[var(--border)] px-2.5 py-1 text-[11px] text-[var(--text-muted)]'>
        暂未启用
      </span>
    </section>
  )
}

export function LingxiBillingPage({
  backHref = '/workspace/lingxi/settings',
}: {
  backHref?: string
}) {
  const [billing, setBilling] = useState<Record<string, any> | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    void api
      .billing()
      .then((result) => setBilling(result.data))
      .catch((cause) => setError(cause instanceof Error ? cause.message : '计费信息暂不可用'))
  }, [])
  const usage = billing?.usage || {}
  return (
    <SettingsShell
      title='计费'
      description='计费与用量沿用原生 Sim 设置契约；灵犀个人工作区当前仅使用内部学习额度。'
    >
      <div className='mb-4'>
        <Link href={backHref} className='text-[12px] text-[var(--text-secondary)] hover:underline'>
          ← 返回设置
        </Link>
      </div>
      {error && <p className='mb-4 text-[12px] text-red-500'>{error}</p>}
      <div className='grid gap-4 md:grid-cols-2'>
        <section className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-5'>
          <p className='text-[11px] text-[var(--text-muted)]'>当前方案</p>
          <h2 className='mt-2 font-medium text-[20px] text-[var(--text-primary)]'>
            {billing?.plan || 'internal'}
          </h2>
          <p className='mt-2 text-[12px] text-[var(--text-muted)]'>
            个人工作区 · 不产生 Stripe 账单
          </p>
        </section>
        <section className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-5'>
          <p className='text-[11px] text-[var(--text-muted)]'>本周期用量</p>
          <h2 className='mt-2 font-medium text-[20px] text-[var(--text-primary)]'>
            {usage.current ?? 0} credits
          </h2>
          <p className='mt-2 text-[12px] text-[var(--text-muted)]'>
            内部额度不计费，当前不启用自动续费。
          </p>
        </section>
      </div>
      <div className='mt-4 grid gap-4 md:grid-cols-2'>
        <PlaceholderCard
          title='付款方式与发票'
          description='LingxiIdentity 账户暂不绑定支付方式。若未来启用计费，会在此接入原生账单门户。'
        />
        <section className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-5'>
          <h2 className='font-medium text-[14px] text-[var(--text-primary)]'>用量明细</h2>
          <p className='mt-2 text-[12px] leading-5 text-[var(--text-muted)]'>
            任务用量以零成本审计记录保留，便于学习过程追踪。
          </p>
          <div className='mt-4 flex gap-3'>
            <Link
              href='/workspace/lingxi/logs'
              className='rounded-[7px] border border-[var(--border)] px-3 py-1.5 text-[12px] text-[var(--text-primary)] hover:bg-[var(--surface-hover)]'
            >
              查看任务日志
            </Link>
            <a
              href='/api/users/me/usage-logs/export?period=30d'
              className='rounded-[7px] border border-[var(--border)] px-3 py-1.5 text-[12px] text-[var(--text-primary)] hover:bg-[var(--surface-hover)]'
            >
              导出 CSV
            </a>
          </div>
        </section>
      </div>
    </SettingsShell>
  )
}

export function LingxiUsagePage({
  backHref = '/account/settings/billing',
}: {
  backHref?: string
} = {}) {
  const [rows, setRows] = useState<Array<Record<string, any>>>([])
  useEffect(() => {
    void api
      .usageLogs('30d')
      .then((result) => setRows(result.logs))
      .catch(() => setRows([]))
  }, [])
  return (
    <SettingsShell
      title='用量明细'
      description='个人工作区的任务用量审计；不提供重跑、充值或套餐切换。'
    >
      <div className='mb-4 flex items-center justify-between'>
        <Link href={backHref} className='text-[12px] text-[var(--text-secondary)] hover:underline'>
          ← 返回计费
        </Link>
        <a
          href='/api/users/me/usage-logs/export?period=30d'
          className='rounded-[7px] border border-[var(--border)] px-3 py-1.5 text-[12px] text-[var(--text-primary)]'
        >
          导出 CSV
        </a>
      </div>
      {rows.length === 0 ? (
        <PlaceholderCard
          title='暂无用量记录'
          description='完成一次学习任务后，这里会显示只读的任务用量审计记录。'
        />
      ) : (
        <div className='overflow-x-auto rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)]'>
          <table className='w-full text-left text-[12px]'>
            <thead>
              <tr className='border-b border-[var(--border)] text-[var(--text-muted)]'>
                <th className='px-4 py-3'>任务</th>
                <th className='px-4 py-3'>来源</th>
                <th className='px-4 py-3'>时间</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={String(row.id)} className='border-b border-[var(--border)] last:border-0'>
                  <td className='px-4 py-3 text-[var(--text-primary)]'>{String(row.id)}</td>
                  <td className='px-4 py-3 text-[var(--text-secondary)]'>{String(row.source)}</td>
                  <td className='px-4 py-3 text-[var(--text-muted)]'>
                    {String(row.createdAt || '')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SettingsShell>
  )
}

export function LingxiUserManagementPage() {
  const [profile, setProfile] = useState<Record<string, any> | null>(null)
  useEffect(() => {
    void api
      .userProfile()
      .then((result) => setProfile(result.user))
      .catch(() => undefined)
  }, [])
  return (
    <SettingsShell
      title='账户与用户管理'
      description='账户资料、登录安全和设备会话由 LingxiIdentity 管理；工作区保持个人私有。'
    >
      <div className='grid gap-4 md:grid-cols-2'>
        <section className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-5'>
          <p className='text-[11px] text-[var(--text-muted)]'>当前账户</p>
          <h2 className='mt-2 font-medium text-[15px] text-[var(--text-primary)]'>
            {profile?.name || '当前用户'}
          </h2>
          <p className='mt-1 text-[12px] text-[var(--text-muted)]'>
            {profile?.email || '由 LingxiIdentity 提供'}
          </p>
          <Link
            href='/account/settings'
            className='mt-4 inline-flex rounded-[7px] border border-[var(--border)] px-3 py-1.5 text-[12px] text-[var(--text-primary)] hover:bg-[var(--surface-hover)]'
          >
            打开账户中心
          </Link>
        </section>
        <PlaceholderCard
          title='成员、邀请与组织'
          description='本版本不实现团队成员、邀请、组织切换、角色管理或成员协作。每位用户只有一个私有 Lingxi 工作区。'
        />
        <PlaceholderCard
          title='管理员控制台'
          description='平台管理员 API 保留为占位，不会在个人工作区暴露封禁、模拟登录或跨用户数据访问。'
        />
        <PlaceholderCard
          title='SSO、API Keys 与凭据'
          description='SSO、凭据、环境变量、API Keys 和外部连接器不属于 Lingxi 工作区能力。'
        />
      </div>
    </SettingsShell>
  )
}

export function LingxiUnavailableSettingsPage({ title }: { title: string }) {
  return (
    <SettingsShell
      title={title}
      description='该原生 Sim 设置面板已保留源码闭包，但当前 LingxiLearn 不启用此能力。'
    >
      <PlaceholderCard
        title={title}
        description='当前功能保留占位实现，后端不会创建或修改对应的工作流、团队或计费资源。'
      />
    </SettingsShell>
  )
}
