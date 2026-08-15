'use client'

import { useEffect, useState } from 'react'
import { createLogger } from '@sim/logger'
import { getErrorMessage } from '@sim/utils/errors'
import { formatQuotedNameList } from '@sim/utils/string'
import { useQueryClient } from '@tanstack/react-query'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { ApiClientError } from '@/lib/api/client/errors'
import { requestJson } from '@/lib/api/client/request'
import { acceptInvitationContract } from '@/lib/api/contracts/invitations'
import { client, useSession } from '@/lib/auth/auth-client'
import { buildAuthCrossLink } from '@/app/(auth)/auth-redirect'
import { InviteLayout, InviteStatusCard } from '@/app/invite/components'
import { useInvitationDetails } from '@/hooks/queries/invitations'
import { organizationKeys } from '@/hooks/queries/organization'
import { refreshSessionQuery } from '@/hooks/queries/session'
import { subscriptionKeys } from '@/hooks/queries/subscription'
import { workspaceKeys } from '@/hooks/queries/workspace'

const logger = createLogger('InviteById')

/** Workspace names listed in the invitation title before collapsing into an "and N more" tail. */
const MAX_LISTED_WORKSPACE_NAMES = 3

/**
 * Goes through the shared builder so the invite page cannot drift from the
 * cross-link shape the auth pages use.
 */
function inviteAuthLink(
  path: '/login' | '/signup',
  callbackUrl: string,
  isNewUser = false
): string {
  return buildAuthCrossLink(path, { callbackUrl, isInviteFlow: true, isNewUser })
}

interface InviteAction {
  label: string
  onClick: () => void
}

interface SignedOutPromptParams {
  registrationDisabled: boolean
  isNewUser: boolean
  callbackUrl: string
  navigate: (href: string) => void
}

/**
 * What a signed-out visitor is offered, as one branch so the copy and the
 * buttons under it can never disagree about what they may do.
 *
 * Under DISABLE_REGISTRATION only signing in is possible — `/signup` rejects
 * the visitor server-side, so offering it would be a dead end.
 */
function signedOutPrompt({
  registrationDisabled,
  isNewUser,
  callbackUrl,
  navigate,
}: SignedOutPromptParams): { description: string; actions: InviteAction[] } {
  const signIn: InviteAction = {
    label: '登录',
    onClick: () => navigate(inviteAuthLink('/login', callbackUrl)),
  }

  if (registrationDisabled) {
    return {
      description: '此实例已关闭账户注册',
      actions: [signIn],
    }
  }

  if (isNewUser) {
    return {
      description: '创建账户以加入此灵犀工作区',
      actions: [
        {
          label: '创建账户',
          onClick: () => navigate(inviteAuthLink('/signup', callbackUrl)),
        },
        { ...signIn, label: '我已有账户' },
      ],
    }
  }

  return {
    description: '登录账户以接受此邀请',
    actions: [
      signIn,
      {
        label: '创建账户',
        onClick: () => navigate(inviteAuthLink('/signup', callbackUrl, true)),
      },
    ],
  }
}

function runBestEffortCacheRefresh(cache: string, refresh: () => Promise<unknown>): void {
  void Promise.resolve()
    .then(refresh)
    .catch((refreshError) => {
      logger.warn('Post-acceptance cache refresh failed', {
        cache,
        error: getErrorMessage(refreshError),
      })
    })
}

type InviteErrorCode =
  | 'missing-token'
  | 'invalid-token'
  | 'expired'
  | 'already-processed'
  | 'email-mismatch'
  | 'workspace-not-found'
  | 'disclosure-outdated'
  | 'user-not-found'
  | 'already-member'
  | 'already-in-organization'
  | 'no-seats-available'
  | 'upgrade-required'
  | 'external-requires-paid-plan'
  | 'invalid-invitation'
  | 'missing-invitation-id'
  | 'server-error'
  | 'unauthorized'
  | 'forbidden'
  | 'network-error'
  | 'unknown'

interface InviteError {
  code: InviteErrorCode
  message: string
  requiresAuth?: boolean
  canRetry?: boolean
}

function getInviteError(code: string): InviteError {
  const errorMap: Record<string, InviteError> = {
    'missing-token': {
      code: 'missing-token',
      message: '邀请链接无效或缺少必要参数。',
    },
    'invalid-token': {
      code: 'invalid-token',
      message: '邀请链接无效或已被使用。',
    },
    expired: {
      code: 'expired',
      message: '此邀请已过期，请请求新的邀请。',
    },
    'already-processed': {
      code: 'already-processed',
      message: '此邀请已被接受或拒绝。',
    },
    'email-mismatch': {
      code: 'email-mismatch',
      message:
        '此邀请发送给了其他邮箱，请使用正确的账户登录。',
      requiresAuth: true,
    },
    'workspace-not-found': {
      code: 'workspace-not-found',
      message: '找不到与此邀请关联的工作区。',
    },
    'disclosure-outdated': {
      code: 'disclosure-outdated',
      message:
        '页面加载后你的工作区发生了变化，请查看最新提示并重新接受邀请。',
      canRetry: true,
    },
    'user-not-found': {
      code: 'user-not-found',
      message: '找不到你的用户账户，请退出后重新登录。',
      requiresAuth: true,
    },
    'already-member': {
      code: 'already-member',
      message: '你已经是此组织或工作区的成员。',
    },
    'already-in-organization': {
      code: 'already-in-organization',
      message:
        '你已经是某个组织的成员，请先离开当前组织再接受新邀请。',
    },
    'no-seats-available': {
      code: 'no-seats-available',
      message:
        '此组织已达到席位上限，请让管理员联系支持团队增加席位后重试。',
      canRetry: true,
    },
    'upgrade-required': {
      code: 'upgrade-required',
      message:
        '工作区所有者需要启用付费套餐并完成计费设置后你才能加入，请让其更新套餐后重试。',
      canRetry: true,
    },
    'external-requires-paid-plan': {
      code: 'external-requires-paid-plan',
      message:
        '外部协作者需要自己的付费套餐。请升级套餐，或让组织以成员身份重新邀请你。',
      canRetry: true,
    },
    'invalid-invitation': {
      code: 'invalid-invitation',
      message: '此邀请无效或已不存在。',
    },
    'not-found': {
      code: 'invalid-invitation',
      message: 'This invitation is invalid or no longer exists.',
    },
    'server-error': {
      code: 'server-error',
      message:
        '处理邀请时发生意外错误，请稍后重试。',
      canRetry: true,
    },
    unauthorized: {
      code: 'unauthorized',
      message: '你需要登录才能接受此邀请。',
      requiresAuth: true,
    },
    forbidden: {
      code: 'forbidden',
      message:
        '你没有权限接受此邀请，请确认使用了正确的账户登录。',
      requiresAuth: true,
    },
    'network-error': {
      code: 'network-error',
      message:
        '无法连接服务器，请检查网络连接后重试。',
      canRetry: true,
    },
  }

  return (
    errorMap[code] || {
      code: 'unknown',
      message:
        '处理邀请时发生意外错误，请重试或联系支持团队。',
      canRetry: true,
    }
  )
}

function codeFromStatus(status: number): InviteErrorCode {
  if (status === 401) return 'unauthorized'
  if (status === 403) return 'forbidden'
  if (status === 404) return 'invalid-invitation'
  if (status === 409) return 'already-in-organization'
  if (status >= 500) return 'server-error'
  return 'unknown'
}

function codeFromApiClientError(error: ApiClientError): string {
  if (error.body && typeof error.body === 'object') {
    const code = (error.body as { error?: unknown }).error
    if (typeof code === 'string' && code.length > 0) return code
  }

  return codeFromStatus(error.status)
}

interface InviteProps {
  /** DISABLE_REGISTRATION. See {@link signedOutPrompt}. */
  registrationDisabled: boolean
}

export default function Invite({ registrationDisabled }: InviteProps) {
  const router = useRouter()
  const params = useParams()
  const inviteId = params.id as string
  const inviteTokenStorageKey = `inviteToken:${inviteId}`
  const searchParams = useSearchParams()
  const { data: session, isPending } = useSession()
  const queryClient = useQueryClient()
  const [actionError, setActionError] = useState<InviteError | null>(null)
  const [isAccepting, setIsAccepting] = useState(false)
  const [accepted, setAccepted] = useState(false)
  /** `undefined` until the effect reads storage; `null` once read and empty. */
  const [storedToken, setStoredToken] = useState<string | null | undefined>(undefined)

  const isNewUser = searchParams.get('new') === 'true'
  const errorReason = searchParams.get('error')
  const urlError = errorReason ? getInviteError(errorReason) : null
  /** `|| null` so an empty `?token=` falls back to storage rather than querying with ''. */
  const tokenFromQuery = searchParams.get('token') || null
  /**
   * Derived during render so the invitation query key is correct on the first
   * commit; an effect-set token refetches under a second key whenever the
   * session cache is already warm at mount.
   */
  const token = tokenFromQuery ?? storedToken ?? null
  const isTokenResolved = tokenFromQuery !== null || storedToken !== undefined

  useEffect(() => {
    if (tokenFromQuery) {
      sessionStorage.setItem(inviteTokenStorageKey, tokenFromQuery)
      return
    }
    setStoredToken(sessionStorage.getItem(inviteTokenStorageKey))
  }, [tokenFromQuery, inviteTokenStorageKey])

  const invitationQuery = useInvitationDetails(inviteId, token, session?.user?.id ?? null, {
    enabled: Boolean(session?.user) && isTokenResolved,
  })
  const invitation = invitationQuery.data?.invitation ?? null
  const joinPreview = invitationQuery.data?.joinPreview ?? null
  const isLoading = Boolean(session?.user) && (!isTokenResolved || invitationQuery.isPending)

  const fetchError = invitationQuery.error
    ? getInviteError(
        invitationQuery.error instanceof ApiClientError
          ? codeFromApiClientError(invitationQuery.error)
          : 'network-error'
      )
    : null
  /**
   * Action errors (accept failures) outrank fetch errors; the URL error param
   * only shows until the invitation loads successfully.
   */
  const error = actionError ?? fetchError ?? (invitationQuery.data ? null : urlError)

  const handleAcceptInvitation = async () => {
    if (!session?.user || !invitation) return
    setIsAccepting(true)

    try {
      const data = await requestJson(acceptInvitationContract, {
        params: { id: inviteId },
        body: {
          token: token ?? undefined,
          /**
           * Disclosure token: acceptance rejects with disclosure-outdated if
           * the sweep set no longer matches what this screen showed. Sent
           * whenever a preview rendered — a no-join preview means the user
           * was shown that nothing moves (an empty disclosed set), which
           * must also conflict if acceptance would sweep anything.
           */
          disclosedWorkspaceIds: joinPreview ? joinPreview.workspaceIdsToMove : undefined,
          disclosedOutcome: joinPreview?.outcome,
        },
      })

      setAccepted(true)
      setIsAccepting(false)
      setTimeout(() => router.push(data.redirectPath), 1200)

      runBestEffortCacheRefresh('session', () => refreshSessionQuery(queryClient))
      runBestEffortCacheRefresh('subscription', () =>
        queryClient.invalidateQueries({ queryKey: subscriptionKeys.all })
      )
      runBestEffortCacheRefresh('organization', () =>
        queryClient.invalidateQueries({ queryKey: organizationKeys.all })
      )
      /**
       * Acceptance can attach the invitee's owned workspaces into the org —
       * the workspace list must not keep serving the stale personal set.
       */
      runBestEffortCacheRefresh('workspaces', () =>
        queryClient.invalidateQueries({ queryKey: workspaceKeys.all })
      )
    } catch (acceptError) {
      logger.error('Error accepting invitation:', acceptError)
      const code =
        acceptError instanceof ApiClientError
          ? codeFromApiClientError(acceptError)
          : 'network-error'
      const serverMessage =
        acceptError instanceof ApiClientError &&
        acceptError.body &&
        typeof acceptError.body === 'object' &&
        typeof (acceptError.body as { message?: unknown }).message === 'string'
          ? ((acceptError.body as { message: string }).message as string)
          : null
      const baseError = getInviteError(code)
      setActionError(
        code === 'server-error' && serverMessage
          ? { ...baseError, message: serverMessage }
          : baseError
      )
      setIsAccepting(false)
    }
  }

  const getCallbackUrl = () => {
    const effectiveToken =
      token || sessionStorage.getItem(inviteTokenStorageKey) || searchParams.get('token')
    return `/invite/${inviteId}${effectiveToken ? `?token=${effectiveToken}` : ''}`
  }

  if (!session?.user && !isPending) {
    const prompt = signedOutPrompt({
      registrationDisabled,
      isNewUser,
      callbackUrl: getCallbackUrl(),
      navigate: router.push,
    })

    return (
      <InviteLayout>
        <InviteStatusCard
          type='login'
          title="You've been invited!"
          description={prompt.description}
          icon='userPlus'
          actions={[
            ...prompt.actions,
            { label: '返回首页', onClick: () => router.push('/') },
          ]}
        />
      </InviteLayout>
    )
  }

  if (isLoading || isPending) {
    return (
      <InviteLayout>
        <InviteStatusCard type='loading' title='' description='正在加载邀请…' />
      </InviteLayout>
    )
  }

  if (error) {
    const callbackUrl = getCallbackUrl()

    if (error.code === 'email-mismatch') {
      return (
        <InviteLayout>
          <InviteStatusCard
            type='warning'
            title='账户不匹配'
            description={error.message}
            icon='userPlus'
            actions={[
              {
                label: '使用其他账户登录',
                onClick: async () => {
                  await client.signOut()
                  router.push(inviteAuthLink('/login', callbackUrl))
                },
              },
              { label: '返回首页', onClick: () => router.push('/') },
            ]}
          />
        </InviteLayout>
      )
    }

    if (error.code === 'already-in-organization') {
      return (
        <InviteLayout>
          <InviteStatusCard
            type='warning'
            title='已经是团队成员'
            description={error.message}
            icon='users'
            actions={[
              { label: '管理团队设置', onClick: () => router.push('/workspace') },
              { label: '返回首页', onClick: () => router.push('/') },
            ]}
          />
        </InviteLayout>
      )
    }

    if (error.requiresAuth) {
      return (
        <InviteLayout>
          <InviteStatusCard
            type='warning'
            title='需要身份验证'
            description={error.message}
            icon='userPlus'
            actions={[
              {
                label: '登录后继续',
                onClick: () => router.push(inviteAuthLink('/login', callbackUrl)),
              },
              ...(registrationDisabled
                ? []
                : [
                    {
                      label: '创建账户',
                      onClick: () => router.push(inviteAuthLink('/signup', callbackUrl)),
                    },
                  ]),
              { label: '返回首页', onClick: () => router.push('/') },
            ]}
          />
        </InviteLayout>
      )
    }

    const actions: Array<{ label: string; onClick: () => void }> = []
    if (error.canRetry) {
      actions.push({ label: '重试', onClick: () => window.location.reload() })
    }
    actions.push({ label: '返回首页', onClick: () => router.push('/') })

    return (
      <InviteLayout>
        <InviteStatusCard
          type='error'
          title='邀请错误'
          description={error.message}
          icon='error'
          isExpiredError={error.code === 'expired'}
          actions={actions}
        />
      </InviteLayout>
    )
  }

  /**
   * Names every granted workspace, not just the primary one — an invitation can
   * span several, and the email already lists them all.
   */
  const grantedWorkspaceNames =
    invitation?.grants
      .map((grant) => grant.workspaceName)
      .filter((name): name is string => Boolean(name)) ?? []
  const displayName =
    invitation?.kind === 'workspace'
      ? grantedWorkspaceNames.length > 0
        ? formatQuotedNameList(grantedWorkspaceNames, MAX_LISTED_WORKSPACE_NAMES)
        : '一个工作区'
      : invitation?.organizationName || '一个组织'

  if (accepted) {
    return (
      <InviteLayout>
        <InviteStatusCard
          type='success'
          title='欢迎！'
          description={`你已成功加入${displayName}，正在跳转…`}
          icon='success'
          actions={[{ label: '返回首页', onClick: () => router.push('/') }]}
        />
      </InviteLayout>
    )
  }

  const isOrg = invitation?.kind === 'organization'

  return (
    <InviteLayout>
      <InviteStatusCard
        type='invitation'
        title={isOrg ? '组织邀请' : '工作区邀请'}
        description={`你受邀加入${displayName}。`}
        icon={isOrg ? 'users' : 'mail'}
        actions={[
          {
            label: '接受邀请',
            onClick: handleAcceptInvitation,
            disabled: isAccepting,
            loading: isAccepting,
          },
          { label: '返回首页', onClick: () => router.push('/') },
        ]}
      />
    </InviteLayout>
  )
}
