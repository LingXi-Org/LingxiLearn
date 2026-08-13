/**
 * Browser-only runtime flags for the LingxiGraph build.
 *
 * Keeping this boundary local prevents server-only deployment state from
 * entering the static browser bundle.
 */
function isTruthy(value: string | undefined): boolean {
  return value !== undefined && ['1', 'true', 'yes', 'on'].includes(value.toLowerCase())
}

export const isHosted = false
export const isChatEnabled = true
export const isReactGrabEnabled = isTruthy(process.env.NEXT_PUBLIC_REACT_GRAB_ENABLED)
export const isReactScanEnabled = isTruthy(process.env.NEXT_PUBLIC_REACT_SCAN_ENABLED)
