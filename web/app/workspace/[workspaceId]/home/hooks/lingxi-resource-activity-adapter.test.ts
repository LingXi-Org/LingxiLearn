import { describe, expect, it } from 'vitest'
import { toResourceActivityNotice } from './lingxi-resource-activity-adapter'

describe('toResourceActivityNotice', () => {
  it('keeps ordinary resource activity transport-neutral', () => {
    expect(toResourceActivityNotice('file:notes')).toEqual({
      resourceId: 'file:notes',
      activation: 'activity',
    })
  })

  it('maps artifact readiness to clearing stale attention', () => {
    expect(toResourceActivityNotice('lingxi-artifact:report', 'artifact.ready')).toEqual({
      resourceId: 'lingxi-artifact:report',
      activation: 'clear',
    })
  })

  it('maps an unlocked delivery to revealing the artifact', () => {
    expect(toResourceActivityNotice('lingxi-artifact:report', 'delivery.unlocked')).toEqual({
      resourceId: 'lingxi-artifact:report',
      activation: 'reveal',
    })
  })
})
