import { afterAll, vi } from 'vitest'
import {
  authMock,
  envFlagsMock,
  envMock,
  hybridAuthMock,
  loggerMock,
  redisConfigMock,
  requestUtilsMock,
  setupGlobalFetchMock,
  setupGlobalStorageMocks,
  urlsMock,
  workflowAuthzMock,
} from '@/tests/support'

/**
 * jest-dom only registers DOM matchers (`toBeVisible`, `toHaveTextContent`, …),
 * so it is dead weight in a `node` environment — which is 985 of the 1,219 test
 * files here. Loading it unconditionally made every one of them pay for it.
 */
if (typeof document !== 'undefined') {
  await import('@testing-library/jest-dom/vitest')
}

setupGlobalFetchMock()
setupGlobalStorageMocks()

vi.mock('@/lib/logger', () => loggerMock)
vi.mock('@/lib/permissions/native/workflow', () => workflowAuthzMock)
vi.mock('@/lib/auth', () => authMock)
vi.mock('@/lib/auth/hybrid', () => hybridAuthMock)
vi.mock('@/lib/core/utils/request', () => requestUtilsMock)
vi.mock('@/lib/core/config/env-flags', () => envFlagsMock)
vi.mock('@/lib/core/config/env', () => envMock)
vi.mock('@/lib/core/utils/urls', () => urlsMock)
vi.mock('@/lib/core/config/redis', () => redisConfigMock)

vi.mock('@/stores/console/store', () => ({
  useConsoleStore: {
    getState: vi.fn().mockReturnValue({
      addConsole: vi.fn(),
    }),
  },
}))

/**
 * The tool registry is 4,351 entries pulling ~5,907 modules, and almost nothing
 * under test needs the real thing — but every test file that transitively
 * reaches it paid to import the whole graph. Measured on the full suite:
 * import 1,347s -> 633s, transform 130s -> 53s.
 *
 * `@/blocks/registry` is mocked the same way directly below, for the same reason.
 *
 * Tests that genuinely assert registration or tool params opt out with
 * `vi.unmock('@/tools/registry')` at the top of the file — see
 * blocks/blocks/outlook.test.ts for the pattern.
 */
vi.mock('@/tools/registry', () => ({ tools: {} }))

vi.mock('@/blocks/registry', () => ({
  getBlock: vi.fn(() => ({
    name: 'Mock Block',
    description: 'Mock block description',
    icon: () => null,
    subBlocks: [],
    outputs: {},
  })),
  getAllBlocks: vi.fn(() => []),
  getLatestBlock: vi.fn(() => undefined),
  /** Mirrors the real module's accessor; without it consumers get "not a function". */
  getBlockRegistry: vi.fn(() => ({})),
  getBlockByToolName: vi.fn((toolName: string) =>
    toolName.startsWith('gmail_')
      ? {
          name: 'Gmail',
          description: 'Gmail integration',
          icon: () => null,
          subBlocks: [],
          outputs: {},
        }
      : undefined
  ),
}))

const originalConsoleError = console.error
const originalConsoleWarn = console.warn

console.error = (...args: any[]) => {
  if (args[0] === 'Workflow execution failed:' && args[1]?.message === 'Test error') {
    return
  }
  if (typeof args[0] === 'string' && args[0].includes('[zustand persist middleware]')) {
    return
  }
  originalConsoleError(...args)
}

console.warn = (...args: any[]) => {
  if (typeof args[0] === 'string' && args[0].includes('[zustand persist middleware]')) {
    return
  }
  originalConsoleWarn(...args)
}

afterAll(() => {
  console.error = originalConsoleError
  console.warn = originalConsoleWarn
})
