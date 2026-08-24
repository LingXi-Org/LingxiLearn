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
    ["import x from '@sim/db'", 'deleted @sim/* package alias'],
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
})
