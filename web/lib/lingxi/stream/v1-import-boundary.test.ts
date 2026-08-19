import { readFileSync } from 'node:fs'
import path from 'node:path'

import { describe, expect, it } from 'vitest'

const V1_MODULES = ['decode-v1.ts', 'turn-model.ts']

describe('V1 stream import boundary', () => {
  it.each(V1_MODULES)('%s does not depend on a V0 or heuristic adapter', (moduleName) => {
    const source = readFileSync(path.resolve(__dirname, moduleName), 'utf8')
    const imports = [...source.matchAll(/(?:from\s+|import\s*)['"]([^'"]+)['"]/g)].map(
      (match) => match[1]
    )
    expect(imports.join('\n')).not.toMatch(/lingxi-graph-adapter|legacy[\\/]v0|(?:^|[\\/-])v0(?:[\\/.-]|$)/i)
  })
})
