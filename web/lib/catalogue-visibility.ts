/**
 * These two original course packs are retained for backend/API compatibility,
 * but are placeholder demos and should not be surfaced by the new workspace UI.
 */
export const HIDDEN_DEMO_MISSION_IDS: ReadonlySet<string> = new Set([
  "web-slow",
  "reliable-delivery",
]);

export function isCatalogueMissionVisible(missionId: string) {
  return !HIDDEN_DEMO_MISSION_IDS.has(missionId);
}
