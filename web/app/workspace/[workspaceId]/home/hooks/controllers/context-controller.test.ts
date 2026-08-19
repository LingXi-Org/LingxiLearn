import { describe, expect, it } from 'vitest'
import { contextOptions, requestMessage } from './context-controller'

describe('Lingxi context boundary', () => {
  it('serializes selections and deduplicates skills', () => {
    const contexts = [
      { kind: 'file' as const, fileId: 'file-1', label: 'Notes' },
      { kind: 'skill' as const, skillId: 'skill-1', label: 'Tutor' },
      { kind: 'skill' as const, skillId: 'skill-1', label: 'Tutor' },
    ]
    expect(contextOptions(contexts)).toEqual({
      resourceRefs: [{ type: 'file', id: 'file-1', label: 'Notes' }],
      skillIds: ['skill-1'],
    })
    expect(requestMessage(' Explain ', contexts)).toContain('[Context]')
  })

  it('enforces the public message limit after context serialization', () => {
    expect(requestMessage('x'.repeat(4100))).toHaveLength(4000)
  })
})
