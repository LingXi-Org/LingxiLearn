import type { AppConfigGateContext } from '@/lib/core/config/appconfig-rules'

/** Per-request evaluation context; same shape as the feature-flag context. */
export type BlockVisibilityContext = AppConfigGateContext

/**
 * The evaluated per-viewer visibility projection.
 *
 * - `revealed` — preview block types this viewer may see.
 * - `disabled` — types whose rule exists but matched no clause; hides
 *   non-preview (shipped) blocks from discovery surfaces (the kill switch).
 * - `previewTagged` — revealed types not globally GA (`enabled !== true`);
 *   the registry appends " (Preview)" to their names.
 *
 * All three are needed: `revealed \ previewTagged` is the "GA'd via config while
 * `preview: true` is still in code" window, and `disabled` targets a disjoint
 * (non-preview) population.
 */
export interface BlockVisibilityState {
  revealed: Set<string>
  disabled: Set<string>
  previewTagged: Set<string>
}
