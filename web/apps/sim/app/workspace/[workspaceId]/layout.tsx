import { ToastProvider } from '@sim/emcn'
import type { LingxiWorkspaceHostContext } from '@/lib/lingxi/types'
import { WorkspaceChrome } from '@/app/workspace/[workspaceId]/components/workspace-chrome'
import { GlobalCommandsProvider } from '@/app/workspace/[workspaceId]/providers/global-commands-provider'
import { WorkspaceHostProvider } from '@/app/workspace/[workspaceId]/providers/workspace-host-provider'
import { LingxiWorkspacePermissionsProvider } from '@/app/workspace/[workspaceId]/providers/lingxi-workspace-permissions-provider'
import { BrandingProvider } from '@/ee/whitelabeling/components/branding-provider'

const LINGXI_HOST_CONTEXT: LingxiWorkspaceHostContext = {
  workspace: {
    id: 'lingxi',
    name: '灵犀智学',
    logoUrl: '/logo_icon_black.svg',
    color: '#f59e0b',
    workspaceMode: 'personal',
    billedAccountUserId: 'lingxi-user',
  },
  hostOrganizationId: null,
  ownerBilling: {
    plan: 'internal',
    status: null,
    isPaid: false,
    isPro: false,
    isTeam: false,
    isEnterprise: false,
    isOrgScoped: false,
    organizationId: null,
    billingInterval: 'month',
    billingBlocked: false,
    billingBlockedReason: null,
  },
  viewer: {
    permission: 'read',
    isHostOrganizationMember: false,
    isHostOrganizationAdmin: false,
  },
}

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi' }]
}

export default async function WorkspaceLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = await params
  const hostContext: LingxiWorkspaceHostContext = {
    ...LINGXI_HOST_CONTEXT,
    workspace: { ...LINGXI_HOST_CONTEXT.workspace, id: workspaceId },
  }

  return (
    <WorkspaceHostProvider
      workspaceId={workspaceId}
      initialContext={hostContext}
      queryEnabled={false}
    >
      <BrandingProvider
        hostOrganizationId={null}
        viewerIsHostOrganizationMember={false}
        initialOrgSettings={null}
      >
        <ToastProvider>
          <GlobalCommandsProvider>
            <div className='flex h-screen w-full flex-col overflow-hidden bg-[var(--surface-1)]'>
              <LingxiWorkspacePermissionsProvider>
                <WorkspaceChrome initialSidebarCollapsed={false}>{children}</WorkspaceChrome>
              </LingxiWorkspacePermissionsProvider>
            </div>
          </GlobalCommandsProvider>
        </ToastProvider>
      </BrandingProvider>
    </WorkspaceHostProvider>
  )
}
