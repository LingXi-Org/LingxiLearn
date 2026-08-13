'use client'

/**
 * The minimum-shell-version takeover for the desktop app.
 *
 * The web app deploys continuously while installed shells lag behind. Bridge
 * changes must normally stay backward compatible (enforced in CI by the
 * desktop-bridge contract audit); when a release is genuinely breaking,
 * `MIN_DESKTOP_VERSION` is bumped and shells below it get this full-screen
 * blocker instead of silently broken features. Renders nothing in browsers
 * and on shells at or above the floor.
 */
export function DesktopUpdateGate() {
  // The Electron updater belongs to Sim's desktop runtime. Lingxi is served
  // as a static web app, so keeping the gate mounted as a no-op preserves the
  // root layout boundary without importing desktop-only runtime code.
  return null
}
