import type { IdentityMe } from './identity-api'

export const MOCK_IDENTITY_ME: IdentityMe = {
  principal: {
    subject: 'local-dev-user',
    tenant_id: 'local-dev-tenant',
    roles: ['user'],
    permissions: ['workspace:read', 'workspace:write'],
    issuer: 'lingxilearn-local',
    audience: ['lingxilearn-local'],
  },
  user: {
    id: 'local-dev-user',
    username: 'local-dev',
    primaryEmail: 'dev@lingxilearn.local',
    email: 'dev@lingxilearn.local',
    name: '本地开发用户',
    emailVerified: true,
    hasPassword: true,
  },
}
