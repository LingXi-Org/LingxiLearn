/**
 * Browser-only runtime flags for the LingxiGraph build.
 *
 * Sim's original flag module also knows about hosting, billing, auth and
 * server-only deployment state. Keeping this boundary local prevents those
 * services from entering the static browser bundle while preserving the
 * feature switches consumed by the copied Sim shell.
 */
function isTruthy(value: string | undefined): boolean {
  return value !== undefined && ['1', 'true', 'yes', 'on'].includes(value.toLowerCase())
}

export const isHosted = false
export const isChatEnabled = true
export const isReactGrabEnabled = isTruthy(process.env.NEXT_PUBLIC_REACT_GRAB_ENABLED)
export const isReactScanEnabled = isTruthy(process.env.NEXT_PUBLIC_REACT_SCAN_ENABLED)
