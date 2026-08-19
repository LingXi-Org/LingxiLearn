/**
 * @vitest-environment jsdom
 */
import { act } from 'react'
import { sleep } from '@/lib/utils/helpers'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { mockRequestJson } = vi.hoisted(() => ({
  mockRequestJson: vi.fn(),
}))

vi.mock('@/lib/api/client/request', () => ({
  requestJson: mockRequestJson,
}))

import {
  getOrganizationRosterContract,
  type OrganizationRoster,
} from '@/lib/api/contracts/organization'
import {
  getOrganizationBillingContract,
  type OrganizationBillingApiResponse,
} from '@/lib/api/contracts/subscription'
import { useOrganizationBilling, useOrganizationRoster } from '@/hooks/queries/organization'

interface Deferred<T> {
  promise: Promise<T>
  resolve: (value: T) => void
}

function createDeferred<T>(): Deferred<T> {
  let resolvePromise: (value: T) => void = () => undefined
  const promise = new Promise<T>((resolve) => {
    resolvePromise = resolve
  })
  return { promise, resolve: resolvePromise }
}

const ROSTER_A: { success: true; data: OrganizationRoster } = {
  success: true,
  data: {
    members: [
      {
        memberId: 'member-a',
        userId: 'user-a',
        role: 'owner',
        createdAt: '2026-01-01T00:00:00.000Z',
        name: 'Member A',
        email: 'member-a@example.com',
        image: null,
        workspaces: [],
      },
    ],
    pendingInvitations: [],
    workspaces: [],
  },
}

const BILLING_A = {
  data: {
    organizationId: 'org-a',
    subscriptionPlan: 'enterprise',
  },
} as OrganizationBillingApiResponse

let container: HTMLDivElement
let root: Root
let queryClient: QueryClient

function OrganizationProbe({ organizationId }: { organizationId: string }) {
  const roster = useOrganizationRoster(organizationId)
  const billing = useOrganizationBilling(organizationId)
  const canManage = Boolean(roster.data && billing.data)

  return (
    <div>
      <span data-testid='member-name'>{roster.data?.members[0]?.name ?? ''}</span>
      <span data-testid='billing-organization'>{billing.data?.data.organizationId ?? ''}</span>
      {canManage && <button type='button'>Manage organization</button>}
    </div>
  )
}

function renderOrganization(organizationId: string) {
  act(() => {
    root.render(
      <QueryClientProvider client={queryClient}>
        <OrganizationProbe organizationId={organizationId} />
      </QueryClientProvider>
    )
  })
}

async function flushQueries() {
  await act(async () => {
    for (let index = 0; index < 5; index++) {
      await Promise.resolve()
      await sleep(0)
    }
  })
}

describe('organization identity transitions', () => {
  beforeEach(() => {
    ;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })
  })

  afterEach(() => {
    act(() => root.unmount())
    queryClient.clear()
    container.remove()
    vi.clearAllMocks()
  })

  it('clears roster and billing while the next org loads', async () => {
    const rosterB = createDeferred<typeof ROSTER_A>()
    const billingB = createDeferred<OrganizationBillingApiResponse>()

    mockRequestJson.mockImplementation(
      (
        contract: unknown,
        input: {
          params?: { id?: string }
          query?: { id?: string }
        }
      ) => {
        if (contract === getOrganizationRosterContract) {
          return input.params?.id === 'org-a' ? Promise.resolve(ROSTER_A) : rosterB.promise
        }
        if (contract === getOrganizationBillingContract) {
          return input.query?.id === 'org-a' ? Promise.resolve(BILLING_A) : billingB.promise
        }
        throw new Error('Unexpected contract')
      }
    )

    renderOrganization('org-a')
    await flushQueries()

    expect(container).toHaveTextContent('Member A')
    expect(container).toHaveTextContent('org-a')
    expect(container.querySelector('button')).toHaveTextContent('Manage organization')

    renderOrganization('org-b')
    await flushQueries()

    expect(container).not.toHaveTextContent('Member A')
    expect(container).not.toHaveTextContent('org-a')
    expect(container.querySelector('button')).toBeNull()
  })
})
