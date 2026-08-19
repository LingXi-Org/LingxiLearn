/**
 * Shared API base configuration.
 *
 * When the app is served by FastAPI (single-process deployment) the API is
 * same-origin and this is empty. Point NEXT_PUBLIC_API_BASE at the backend
 * when running ``next dev`` against a separately hosted server.
 *
 * This module is the single owner of the API_BASE constant. Both the
 * transport layer and domain clients import from here (issue #40).
 */

const configuredApiBase = process.env.NEXT_PUBLIC_API_BASE?.trim()
export const API_BASE = configuredApiBase || ''
