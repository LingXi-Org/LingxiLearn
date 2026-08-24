/**
 * Shared API base configuration.
 *
 * The browser normally uses an empty base so `/api/*` stays same-origin and
 * the Next standalone/dev server rewrites it to FastAPI. A non-empty public
 * base is exceptional cross-origin development compatibility; LingxiIdentity
 * browser requests must remain same-origin.
 *
 * This module is the single owner of the API_BASE constant. Both the
 * transport layer and domain clients import from here (issue #40).
 */

const configuredApiBase = process.env.NEXT_PUBLIC_API_BASE?.trim()
export const API_BASE = configuredApiBase || ''
