import type { ResourceActivityNotice } from './use-workspace-panel-controller'

export function toResourceActivityNotice(
  resourceId: string,
  eventKind?: 'artifact.ready' | 'delivery.unlocked'
): ResourceActivityNotice {
  if (!resourceId.startsWith('lingxi-artifact:')) {
    return { resourceId, activation: 'activity' }
  }
  return {
    resourceId,
    activation: eventKind === 'delivery.unlocked' ? 'reveal' : 'clear',
  }
}
