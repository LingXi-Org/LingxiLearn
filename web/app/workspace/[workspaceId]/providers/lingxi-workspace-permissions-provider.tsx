'use client'

// Keep one native read-only permission boundary. The implementation lives next
// to the shared context hooks so consumers cannot accidentally mount a second
// provider with a different default value.
export { LingxiWorkspacePermissionsProvider } from './workspace-permissions-provider'
