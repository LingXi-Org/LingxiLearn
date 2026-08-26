import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { findQualityBoundaryViolations } from './check-quality-boundaries'

describe('production quality boundaries', () => {
  const fixture = () => mkdtempSync(join(tmpdir(), 'lingxi-quality-boundary-'))

  it('accepts native, strictly checked production source', () => {
    const root = fixture()
    try {
      mkdirSync(join(root, 'app'), { recursive: true })
      writeFileSync(join(root, 'app', 'page.tsx'), "import x from '@/lib/native'\nexport default x\n")
      expect(findQualityBoundaryViolations(root)).toEqual([])
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })

  it.each([
    [`import x from '${['@', 'sim/db'].join('')}'`, 'deleted @sim/* package alias'],
    [
      "import type { WorkspaceFolder } from '@/stores/folders/types'",
      'domain types must not be owned by a store',
    ],
    ['// @ts-nocheck\nexport const x = 1', '@ts-nocheck disables production checking'],
    ['export default { compilerOptions: { noCheck: true } }', 'TypeScript noCheck bypass'],
    ['export default { typescript: { ignoreBuildErrors: true } }', 'Next.js ignoreBuildErrors bypass'],
  ])('rejects %s', (source, rule) => {
    const root = fixture()
    try {
      mkdirSync(join(root, 'app'), { recursive: true })
      writeFileSync(join(root, 'app', 'page.tsx'), source)
      expect(findQualityBoundaryViolations(root)).toEqual([
        expect.objectContaining({ file: 'app/page.tsx', rule }),
      ])
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })

  it('rejects a restored fake compatibility route', () => {
    const root = fixture()
    try {
      const route = join(root, 'app', 'desktop', 'auth', 'page.tsx')
      mkdirSync(join(root, 'app', 'desktop', 'auth'), { recursive: true })
      writeFileSync(route, 'export default function FakeRoute() { return null }')
      expect(findQualityBoundaryViolations(root)).toContainEqual({
        file: 'app/desktop/auth/page.tsx',
        rule: 'removed fake compatibility route was restored',
      })
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })

  it('rejects restored API facade and workflow-editor source', () => {
    const root = fixture()
    try {
      const facade = join(root, 'lib', 'lingxi', 'api.ts')
      const workflowEditor = join(
        root,
        'app',
        'workspace',
        '[workspaceId]',
        'w',
        'components',
        'sidebar.tsx'
      )
      mkdirSync(join(facade, '..'), { recursive: true })
      mkdirSync(join(workflowEditor, '..'), { recursive: true })
      writeFileSync(facade, 'export const api = {}')
      writeFileSync(workflowEditor, 'export function Sidebar() { return null }')

      expect(findQualityBoundaryViolations(root)).toEqual(
        expect.arrayContaining([
          {
            file: 'lib/lingxi/api.ts',
            rule: 'removed compatibility source was restored',
          },
          {
            file: 'app/workspace/[workspaceId]/w',
            rule: 'removed compatibility source tree was restored',
          },
        ])
      )
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })

  it('rejects unsupported credential tags in the chat renderer', () => {
    const root = fixture()
    try {
      const specialTags = join(
        root,
        'app',
        'workspace',
        '[workspaceId]',
        'home',
        'components',
        'message-content',
        'components',
        'special-tags',
        'special-tags.tsx'
      )
      mkdirSync(join(specialTags, '..'), { recursive: true })
      writeFileSync(specialTags, "export const types = ['browser_takeover', 'service_account']")

      expect(findQualityBoundaryViolations(root)).toContainEqual({
        file: 'app/workspace/[workspaceId]/home/components/message-content/components/special-tags/special-tags.tsx',
        rule: "unsupported credential tag 'service_account' was restored",
      })
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })

  it('rejects fake native task mutation shims', () => {
    const root = fixture()
    try {
      const chatQueries = join(root, 'hooks', 'queries', 'mothership-chats.ts')
      mkdirSync(join(chatQueries, '..'), { recursive: true })
      writeFileSync(
        chatQueries,
        "export const mutation = { mutationFn: async () => undefined }"
      )

      expect(findQualityBoundaryViolations(root)).toContainEqual({
        file: 'hooks/queries/mothership-chats.ts',
        rule: 'native task mutations must not use fake success or unsupported shims',
      })
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })

  it('requires shared Workspace copy owners to use the product catalog', () => {
    const root = fixture()
    try {
      const owner = join(
        root,
        'app',
        'workspace',
        '[workspaceId]',
        'components',
        'resource',
        'resource.tsx'
      )
      mkdirSync(join(owner, '..'), { recursive: true })
      writeFileSync(owner, "export const title = 'Files'")
      expect(findQualityBoundaryViolations(root)).toContainEqual({
        file: 'app/workspace/[workspaceId]/components/resource/resource.tsx',
        rule: 'shared Workspace copy must use the product catalog',
      })

      writeFileSync(owner, "import { workspaceCopy } from '@/lib/product-copy'\nvoid workspaceCopy")
      expect(findQualityBoundaryViolations(root)).toEqual([])
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })

  it('rejects raw technical errors even when a Workspace component imports the catalog', () => {
    const root = fixture()
    try {
      const file = join(root, 'app', 'workspace', '[workspaceId]', 'files', 'page.tsx')
      mkdirSync(join(file, '..'), { recursive: true })
      writeFileSync(
        file,
        "import { workspaceCopy } from '@/lib/product-copy'\nsetError(error.message)\nvoid workspaceCopy"
      )
      expect(findQualityBoundaryViolations(root)).toContainEqual({
        file: 'app/workspace/[workspaceId]/files/page.tsx',
        rule: 'raw technical error exposed in Workspace UI',
      })
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })

  it.each([
    'setEditAddressError(getErrorMessage(error))',
    'toast.error(toError(error).message)',
    'const view = <p>{getErrorMessage(error)}</p>',
  ])('rejects additional raw-error UI sink: %s', (sink) => {
    const root = fixture()
    try {
      const file = join(root, 'app', 'workspace', '[workspaceId]', 'settings', 'page.tsx')
      mkdirSync(join(file, '..'), { recursive: true })
      writeFileSync(file, sink)
      expect(findQualityBoundaryViolations(root)).toContainEqual({
        file: 'app/workspace/[workspaceId]/settings/page.tsx',
        rule: 'raw technical error exposed in Workspace UI',
      })
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })
})
