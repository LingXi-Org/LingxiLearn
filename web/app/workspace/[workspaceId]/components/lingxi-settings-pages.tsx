'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { api } from '@/lib/lingxi/api'
import { SettingsPanel } from '@/app/workspace/[workspaceId]/settings/components/settings-panel'

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
    <SettingsPanel title={title} description={description}>
      <div className='w-full py-2'>
        <div className='mx-auto w-full max-w-[900px]'>{children}</div>
      </div>
    </SettingsPanel>
  )
}

/**
 * The only user-management surface the LingxiLearn product closure keeps
 * (issue #54): account identity is real (LingxiIdentity + `/api/users/me/*`),
 * while members/invites/organizations have no backend owner and were removed
 * instead of rendering placeholders.
 */
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
      <section className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-5'>
        <p className='text-[11px] text-[var(--text-muted)]'>当前账户</p>
        <h2 className='mt-2 font-medium text-[15px] text-[var(--text-primary)]'>
          {profile?.name || '当前用户'}
        </h2>
        <p className='mt-1 text-[12px] text-[var(--text-muted)]'>
          {profile?.email || '由 LingxiIdentity 提供'}
        </p>
        <p className='mt-2 text-[12px] leading-5 text-[var(--text-muted)]'>
          每位用户只有一个私有 LingXi 工作区；成员、邀请与组织协作不属于当前产品能力。
        </p>
        <Link
          href='/account/settings'
          className='mt-4 inline-flex rounded-[7px] border border-[var(--border)] px-3 py-1.5 text-[12px] text-[var(--text-primary)] hover:bg-[var(--surface-hover)]'
        >
          打开账户中心
        </Link>
      </section>
    </SettingsShell>
  )
}
