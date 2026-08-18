'use client'

import { useEffect } from 'react'
import dynamic from 'next/dynamic'
import { redirect } from 'next/navigation'
import { usePostHog } from 'posthog-js/react'
import { useSession } from '@/lib/auth/auth-client'
import { captureEvent } from '@/lib/posthog/client'
import { LingxiResourcePage } from '@/app/workspace/[workspaceId]/components/lingxi-resource-page'
import { LingxiUserManagementPage } from '@/app/workspace/[workspaceId]/components/lingxi-settings-pages'
import { useWorkspaceHostContext } from '@/app/workspace/[workspaceId]/providers/workspace-host-provider'
import { General } from '@/app/workspace/[workspaceId]/settings/components/general/general'
import { SettingsSectionProvider } from '@/app/workspace/[workspaceId]/settings/components/settings-panel'
import {
  getSettingsSectionMeta,
  isBillingEnabled,
  type SettingsSection,
} from '@/app/workspace/[workspaceId]/settings/navigation'

const NotIntegratedSection = ({ title }: { title: string }) => (
  <main className='flex min-h-[240px] items-center justify-center p-8'>
    <p className='text-sm text-[var(--text-secondary)]'>{title}暂未开放。</p>
  </main>
)

const BYOK = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/byok/byok').then((m) => m.BYOK)
)
const Forks = (_props: any) => <NotIntegratedSection title='工作区分支' />
const Secrets = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/secrets/secrets').then((m) => m.Secrets)
)
const Sandboxes = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/sandboxes/sandboxes').then(
    (m) => m.Sandboxes
  )
)
const CustomTools = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/custom-tools/custom-tools').then(
    (m) => m.CustomTools
  )
)
const Inbox = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/inbox/inbox').then((m) => m.Inbox)
)
const MCP = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/mcp/mcp').then((m) => m.MCP)
)
const RecentlyDeleted = dynamic(() =>
  import(
    '@/app/workspace/[workspaceId]/settings/components/recently-deleted/recently-deleted'
  ).then((m) => m.RecentlyDeleted)
)
const SelfHost = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/self-host/self-host').then(
    (m) => m.SelfHost
  )
)
const Billing = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/billing/billing').then((m) => m.Billing)
)
const Teammates = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/teammates/teammates').then(
    (m) => m.Teammates
  )
)
const TeamManagement = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/team-management/team-management').then(
    (m) => m.TeamManagement
  )
)
const WorkflowMcpServers = dynamic(() =>
  import(
    '@/app/workspace/[workspaceId]/settings/components/workflow-mcp-servers/workflow-mcp-servers'
  ).then((m) => m.WorkflowMcpServers)
)
const AccessControl = (_props: any) => <NotIntegratedSection title='访问控制' />
const CustomBlocks = (_props: any) => <NotIntegratedSection title='自定义模块' />
const AuditLogs = (_props: any) => <NotIntegratedSection title='审计日志' />
const SSO = (_props: any) => <NotIntegratedSection title='单点登录' />
const SessionPolicySettings = (_props: any) => <NotIntegratedSection title='会话策略' />
const DataRetentionSettings = (_props: any) => <NotIntegratedSection title='数据保留' />
const DataDrainsSettings = (_props: any) => <NotIntegratedSection title='数据导出' />
const Desktop = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/desktop/desktop').then((m) => m.Desktop)
)
const Browser = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/browser/browser').then((m) => m.Browser)
)
const Terminal = dynamic(() =>
  import('@/app/workspace/[workspaceId]/settings/components/terminal/terminal').then(
    (m) => m.Terminal
  )
)
const WhitelabelingSettings = (_props: any) => <NotIntegratedSection title='品牌设置' />

interface SettingsPageProps {
  section: SettingsSection
}

export function SettingsPage({ section }: SettingsPageProps) {
  const { isPending: sessionLoading } = useSession()
  const hostContext = useWorkspaceHostContext()
  const posthog = usePostHog()

  const normalizedSection: SettingsSection =
    (section as string) === 'subscription' ? 'billing' : section
  // admin/mothership/apikeys surfaces were removed with their Sim closures
  // (issue #54): those paths have no section here, so billing gating is the
  // only normalization left.
  const effectiveSection =
    !isBillingEnabled && (normalizedSection === 'billing' || normalizedSection === 'organization')
      ? 'general'
      : normalizedSection
  const organizationId = hostContext.hostOrganizationId
  const meta = getSettingsSectionMeta(effectiveSection)

  useEffect(() => {
    if (sessionLoading) return
    captureEvent(posthog, 'settings_tab_viewed', {
      plane: 'workspace',
      section: effectiveSection,
    })
  }, [effectiveSection, sessionLoading, posthog])

  // Lingxi deliberately reuses Sim's resource chrome and controls, but it has
  // a different settings contract: learning preferences and the private
  // workspace are native resources, while canvas/workflow settings are not.
  // The capability registry (issue #54) is the source of truth: only
  // general/teammates have a real backend owner, so any other section is not
  // rendered as a placeholder — it simply does not exist as a destination.
  if (hostContext.workspace.id === 'lingxi') {
    if (effectiveSection === 'general') return <LingxiResourcePage kind='settings' />
    if (effectiveSection === 'teammates') return <LingxiUserManagementPage />
    redirect(`/workspace/${hostContext.workspace.id}/settings`)
  }

  return (
    <SettingsSectionProvider section={effectiveSection} meta={meta ?? undefined}>
      {effectiveSection === 'general' && <General />}
      {effectiveSection === 'desktop' && <Desktop />}
      {effectiveSection === 'browser' && <Browser />}
      {effectiveSection === 'terminal' && <Terminal />}
      {effectiveSection === 'secrets' && <Secrets />}
      {effectiveSection === 'access-control' && organizationId && (
        <AccessControl
          organizationId={organizationId}
          isOrganizationAdmin={hostContext.viewer.isHostOrganizationAdmin}
        />
      )}
      {effectiveSection === 'custom-blocks' && <CustomBlocks />}
      {effectiveSection === 'audit-logs' && organizationId && (
        <AuditLogs organizationId={organizationId} />
      )}
      {isBillingEnabled && effectiveSection === 'billing' && (
        <Billing
          scope={organizationId ? 'organization' : 'account'}
          organizationId={organizationId ?? undefined}
          governingWorkspaceName={hostContext.workspace.name}
          creditUsageHref={`/workspace/${hostContext.workspace.id}/settings/billing/credit-usage`}
        />
      )}
      {effectiveSection === 'teammates' && <Teammates />}
      {isBillingEnabled && effectiveSection === 'organization' && organizationId && (
        <TeamManagement
          billingHref={`/workspace/${hostContext.workspace.id}/settings/billing`}
        />
      )}
      {effectiveSection === 'sso' && organizationId && <SSO organizationId={organizationId} />}
      {effectiveSection === 'sessions' && organizationId && (
        <SessionPolicySettings key={organizationId} organizationId={organizationId} />
      )}
      {effectiveSection === 'data-retention' && organizationId && (
        <DataRetentionSettings organizationId={organizationId} />
      )}
      {effectiveSection === 'data-drains' && organizationId && (
        <DataDrainsSettings organizationId={organizationId} />
      )}
      {effectiveSection === 'whitelabeling' && organizationId && (
        <WhitelabelingSettings organizationId={organizationId} />
      )}
      {effectiveSection === 'byok' && <BYOK />}
      {effectiveSection === 'sandboxes' && <Sandboxes />}
      {effectiveSection === 'mcp' && <MCP />}
      {effectiveSection === 'forks' && <Forks />}
      {effectiveSection === 'custom-tools' && <CustomTools />}
      {effectiveSection === 'workflow-mcp-servers' && <WorkflowMcpServers />}
      {effectiveSection === 'inbox' && <Inbox />}
      {effectiveSection === 'recently-deleted' && <RecentlyDeleted />}
      {effectiveSection === 'self-host' && <SelfHost />}
    </SettingsSectionProvider>
  )
}
