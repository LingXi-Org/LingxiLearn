import { cookies } from 'next/headers'
import { notFound } from 'next/navigation'
import { ToastProvider } from '@/components/ui-kit'
import { isLingxiWorkspaceId, LINGXI_WORKSPACE_ID } from '@/lib/lingxi/capabilities'
import type { LingxiWorkspaceHostContext } from '@/lib/lingxi/types'
import { inter } from '@/app/_styles/fonts/inter/inter'
import { WorkspaceAuthGuard } from '@/app/workspace/workspace-auth-guard'
import { WorkspaceChrome } from './components/workspace-chrome'
import { GlobalCommandsProvider } from './providers/global-commands-provider'
import { LingxiWorkspacePermissionsProvider } from './providers/lingxi-workspace-permissions-provider'
import { WorkspaceHostProvider } from './providers/workspace-host-provider'

const LINGXI_HOST_CONTEXT: LingxiWorkspaceHostContext = {
  workspace: {
    id: LINGXI_WORKSPACE_ID,
    name: '灵犀智学',
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

export const dynamicParams = false

export function generateStaticParams() {
  return [{ workspaceId: LINGXI_WORKSPACE_ID }]
}

export default async function WorkspaceLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ workspaceId: string }>
}) {
  const { workspaceId } = await params
  if (!isLingxiWorkspaceId(workspaceId)) notFound()
  const initialSidebarCollapsed = (await cookies()).get('sidebar_collapsed')?.value === '1'

  return (
    <WorkspaceAuthGuard>
      <WorkspaceHostProvider
        workspaceId={workspaceId}
        initialContext={LINGXI_HOST_CONTEXT}
        queryEnabled={false}
      >
        <ToastProvider>
          <GlobalCommandsProvider>
            <div
              className={`${inter.variable} flex h-screen min-h-0 w-full max-w-none flex-col overflow-hidden bg-[var(--surface-1)]`}
            >
              <LingxiWorkspacePermissionsProvider>
                <WorkspaceChrome initialSidebarCollapsed={initialSidebarCollapsed}>
                  {children}
                </WorkspaceChrome>
              </LingxiWorkspacePermissionsProvider>
            </div>
          </GlobalCommandsProvider>
        </ToastProvider>
      </WorkspaceHostProvider>
    </WorkspaceAuthGuard>
  )
}
