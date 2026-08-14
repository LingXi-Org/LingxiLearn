'use client'

import { useEffect } from 'react'
import dynamic from 'next/dynamic'
import { usePostHog } from 'posthog-js/react'
import type { OrganizationSettingsSection } from '@/components/settings/navigation'
import { captureEvent } from '@/lib/posthog/client'

const NotIntegratedSection = ({ title }: { title: string }) => (
  <main className='flex min-h-[240px] items-center justify-center p-8'>
    <p className='text-sm text-[var(--text-secondary)]'>{title}暂未开放。</p>
  </main>
)

const TeamManagement = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/team-management/team-management').then(
    (module) => module.TeamManagement
  )
)
const Billing = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/billing/billing').then(
    (module) => module.Billing
  )
)
const AccessControl = (_props: any) => <NotIntegratedSection title='访问控制' />
const AuditLogs = (_props: any) => <NotIntegratedSection title='审计日志' />
const SSO = (_props: any) => <NotIntegratedSection title='单点登录' />
const SessionPolicySettings = (_props: any) => <NotIntegratedSection title='会话策略' />
const DataRetentionSettings = (_props: any) => <NotIntegratedSection title='数据保留' />
const DataDrainsSettings = (_props: any) => <NotIntegratedSection title='数据导出' />
const WhitelabelingSettings = (_props: any) => <NotIntegratedSection title='品牌设置' />

interface OrganizationSettingsRendererProps {
  organizationId: string
  section: OrganizationSettingsSection
}

export function OrganizationSettingsRenderer({
  organizationId,
  section,
}: OrganizationSettingsRendererProps) {
  const posthog = usePostHog()

  useEffect(() => {
    captureEvent(posthog, 'settings_tab_viewed', { plane: 'organization', section })
  }, [posthog, section])

  if (section === 'members') return <TeamManagement organizationId={organizationId} />
  if (section === 'billing') return <Billing scope='organization' organizationId={organizationId} />
  if (section === 'access-control') {
    return <AccessControl organizationId={organizationId} isOrganizationAdmin />
  }
  if (section === 'audit-logs') return <AuditLogs organizationId={organizationId} />
  if (section === 'sso') return <SSO organizationId={organizationId} />
  if (section === 'sessions') {
    return <SessionPolicySettings key={organizationId} organizationId={organizationId} />
  }
  if (section === 'data-retention') {
    return <DataRetentionSettings organizationId={organizationId} />
  }
  if (section === 'data-drains') return <DataDrainsSettings organizationId={organizationId} />
  return <WhitelabelingSettings organizationId={organizationId} />
}
