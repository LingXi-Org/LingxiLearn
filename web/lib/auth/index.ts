export {
  client,
  signOut,
  startLogin,
  startRegistration,
  startSocialLogin,
  useActiveOrganization,
  useSession,
  useSubscription,
} from './auth-client'
export type { AuthRedirectOptions, AuthRedirectResult, SocialAuthOptions } from './auth-client'
export type {
  IdentityMe,
  IdentityPrincipal,
  IdentitySession,
  IdentityUser,
  VerificationRecord,
} from './identity-api'
export { IdentityApiError, identityApi } from './identity-api'
export { SessionProvider, useSession as useIdentitySession } from './session-provider'
export { getSession } from './session-server'
