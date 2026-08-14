export async function isForkingAvailableForWorkspace(
  _organizationId?: string | null,
  _userId?: string
): Promise<boolean> {
  return false
}

function unavailable(): never {
  throw new Error('工作区分支功能未接入 LingxiGraph')
}

export const assertCanUnlink = unavailable
export const assertCanFork = unavailable
export const assertCanRollback = unavailable
export const assertWorkspaceAdminAccess = unavailable
export const assertCanPromote = unavailable
