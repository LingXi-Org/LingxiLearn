import { createLogger } from '@/lib/logger'
import { type NextRequest, NextResponse } from 'next/server'
import { sendToProfound } from './lib/analytics/profound'
import { getEnv } from './lib/core/config/env'
import { isAuthDisabled, isMockAuthEnabled } from './lib/core/config/env-flags'
import { generateRuntimeCSP } from './lib/core/security/csp'
import { getClientIp } from './lib/core/utils/request'
import { isNonCanonicalSimHost } from './lib/core/utils/urls'

const logger = createLogger('Proxy')

/** The production browser session is the host-only BFF cookie. */
export const BFF_SESSION_COOKIE = 'lingxi_session'

function hasBffSession(request: NextRequest): boolean {
  return Boolean(request.cookies.get(BFF_SESSION_COOKIE)?.value)
}

export interface CorsPolicy {
  origin: string
  credentials: boolean
  methods: string
  headers: string
}

const DEFAULT_API_ALLOWED_HEADERS =
  'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version, X-API-Key, Authorization'

const WORKFLOW_EXECUTE_HEADERS =
  'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version, X-API-Key, X-Execution-Id, X-Execution-Mode, X-Execution-Timeout-Seconds'

/** v2 execute: run identity and modes use the v2 wire names while streaming negotiates its protocol. */
const WORKFLOW_EXECUTE_V2_HEADERS =
  'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version, X-API-Key, X-Run-Id, X-Sim-Stream-Protocol'

/** Subpaths under /api/chat/* that serve the workspace UI, not embeds. */
const EMBED_RESERVED_SEGMENTS = new Set(['manage', 'validate'])

/** True for /api/chat/[identifier] and any deeper subroute. */
function isEmbedPath(pathname: string): boolean {
  const segments = pathname.split('/')
  if (segments.length < 4) return false
  if (segments[1] !== 'api') return false
  if (segments[2] !== 'chat') return false
  const identifier = segments[3]
  if (!identifier || EMBED_RESERVED_SEGMENTS.has(identifier)) return false
  return true
}

interface CorsRule {
  match: (pathname: string) => boolean
  policy: (request: NextRequest) => CorsPolicy
}

const CORS_RULES: readonly CorsRule[] = [
  {
    match: (p) => p.startsWith('/api/auth/oauth2/'),
    policy: () => ({
      origin: '*',
      credentials: false,
      methods: 'GET, POST, OPTIONS',
      headers: 'Content-Type, Authorization, Accept',
    }),
  },
  {
    match: (p) => p === '/api/mcp/copilot',
    policy: () => ({
      origin: '*',
      credentials: false,
      methods: 'GET, POST, OPTIONS, DELETE',
      headers: 'Content-Type, Authorization, X-API-Key, X-Requested-With, Accept',
    }),
  },
  {
    match: (p) => isEmbedPath(p),
    policy: (request) => {
      const requestOrigin = request.headers.get('origin')
      return {
        origin: requestOrigin || '*',
        credentials: !!requestOrigin,
        methods: 'GET, POST, PUT, OPTIONS',
        headers: 'Content-Type, X-Requested-With',
      }
    },
  },
  {
    match: (p) => /^\/api\/workflows\/[^/]+\/execute$/.test(p),
    policy: () => ({
      origin: '*',
      credentials: false,
      methods: 'GET,POST,OPTIONS,PUT',
      headers: WORKFLOW_EXECUTE_HEADERS,
    }),
  },
  {
    // Mirrors the v1 rule: public execute endpoints are wildcard-origin and
    // credential-free — the default credentialed policy would both block
    // browser API-key calls and open a cookie-bearing CSRF surface.
    match: (p) => /^\/api\/v2\/workflows\/[^/]+\/execute$/.test(p),
    policy: () => ({
      origin: '*',
      credentials: false,
      methods: 'POST,OPTIONS',
      headers: WORKFLOW_EXECUTE_V2_HEADERS,
    }),
  },
]

/** Single source of truth for /api/* CORS — resolved at request time, not baked at build. */
export function resolveApiCorsPolicy(request: NextRequest): CorsPolicy {
  const { pathname } = request.nextUrl
  for (const rule of CORS_RULES) {
    if (rule.match(pathname)) return rule.policy(request)
  }
  return {
    origin: getEnv('NEXT_PUBLIC_APP_URL') || 'http://localhost:3001',
    credentials: true,
    methods: 'GET,POST,OPTIONS,PUT,DELETE',
    headers: DEFAULT_API_ALLOWED_HEADERS,
  }
}

const CORS_PREFLIGHT_MAX_AGE = '86400'

function applyCorsHeaders(response: NextResponse, policy: CorsPolicy): void {
  response.headers.set('Access-Control-Allow-Origin', policy.origin)
  response.headers.set('Access-Control-Allow-Credentials', String(policy.credentials))
  response.headers.set('Access-Control-Allow-Methods', policy.methods)
  response.headers.set('Access-Control-Allow-Headers', policy.headers)
  if (policy.origin !== '*') {
    response.headers.set('Vary', 'Origin')
  }
}

/** Next's auto-OPTIONS doesn't carry middleware headers, so we answer preflight here. */
function buildPreflightResponse(policy: CorsPolicy): NextResponse {
  const response = new NextResponse(null, { status: 204 })
  applyCorsHeaders(response, policy)
  response.headers.set('Access-Control-Max-Age', CORS_PREFLIGHT_MAX_AGE)
  return response
}

const SUSPICIOUS_UA_PATTERNS = [
  /^\s*$/, // Empty user agents
  /\.\./, // Path traversal attempt
  /<\s*script/i, // Potential XSS payloads
  /^\(\)\s*{/, // Command execution attempt
  /\b(sqlmap|nikto|gobuster|dirb|nmap)\b/i, // Known scanning tools
] as const

/**
 * Handles authentication-based redirects for root paths
 */
function handleRootPathRedirects(
  request: NextRequest,
  hasActiveSession: boolean
): NextResponse | null {
  const url = request.nextUrl

  if (url.pathname !== '/') {
    return null
  }

  // The product homepage is public. Workspace entry is explicit via
  // /workspace, so an existing or mock session must not hijack the landing page.
  return null
}

/**
 * Handles security filtering for suspicious user agents
 */
function handleSecurityFiltering(request: NextRequest): NextResponse | null {
  const userAgent = request.headers.get('user-agent') || ''
  const { pathname } = request.nextUrl
  const isWebhookEndpoint =
    pathname.startsWith('/api/webhooks/trigger/') ||
    pathname.startsWith('/api/webhooks/tiktok') ||
    pathname.startsWith('/api/webhooks/agentmail')
  const isMcpEndpoint = pathname.startsWith('/api/mcp/')
  const isMcpOauthDiscoveryEndpoint =
    pathname.startsWith('/.well-known/oauth-authorization-server') ||
    pathname.startsWith('/.well-known/oauth-protected-resource')
  const isSuspicious = SUSPICIOUS_UA_PATTERNS.some((pattern) => pattern.test(userAgent))

  // Block suspicious requests, but exempt machine-to-machine endpoints that may
  // legitimately omit User-Agent headers (webhooks and MCP protocol discovery/calls).
  if (isSuspicious && !isWebhookEndpoint && !isMcpEndpoint && !isMcpOauthDiscoveryEndpoint) {
    logger.warn('Blocked suspicious request', {
      userAgent,
      ip: getClientIp(request),
      url: request.url,
      method: request.method,
      pattern: SUSPICIOUS_UA_PATTERNS.find((pattern) => pattern.test(userAgent))?.toString(),
    })

    return new NextResponse(null, {
      status: 403,
      statusText: 'Forbidden',
      headers: {
        'Content-Type': 'text/plain',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Content-Security-Policy': "default-src 'none'",
        'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
        Pragma: 'no-cache',
        Expires: '0',
      },
    })
  }

  return null
}

export async function proxy(request: NextRequest) {
  const url = request.nextUrl

  if (url.pathname.startsWith('/api/')) {
    const policy = resolveApiCorsPolicy(request)
    if (request.method === 'OPTIONS') {
      return buildPreflightResponse(policy)
    }
    const response = NextResponse.next()
    applyCorsHeaders(response, policy)
    return response
  }

  const hasActiveSession = isAuthDisabled || isMockAuthEnabled || hasBffSession(request)

  const redirect = handleRootPathRedirects(request, hasActiveSession)
  if (redirect) return track(request, redirect)

  if (url.pathname === '/login' || url.pathname === '/signup') {
    // These are public entry points. Do not infer authentication from a stale
    // cookie: the BFF may correctly return 401 and the page must still render.
    // Protected routes below perform the login redirect instead.
    const response = NextResponse.next()
    response.headers.set('Content-Security-Policy', generateRuntimeCSP())
    response.headers.set('X-Content-Type-Options', 'nosniff')
    response.headers.set('X-Frame-Options', 'SAMEORIGIN')
    return track(request, response)
  }

  // Chat pages are publicly accessible embeds — CSP is set in next.config.ts headers
  if (url.pathname.startsWith('/chat/')) {
    return track(request, NextResponse.next())
  }

  if (url.pathname.startsWith('/workspace')) {
    if (!hasActiveSession) {
      return track(request, NextResponse.redirect(new URL('/login', request.url)))
    }
    const response = NextResponse.next()
    response.headers.set('Content-Security-Policy', generateRuntimeCSP())
    response.headers.set('X-Content-Type-Options', 'nosniff')
    response.headers.set('X-Frame-Options', 'SAMEORIGIN')
    return track(request, response)
  }

  const securityBlock = handleSecurityFiltering(request)
  if (securityBlock) return track(request, securityBlock)

  const response = NextResponse.next()
  response.headers.set('Vary', 'User-Agent')

  response.headers.set('Content-Security-Policy', generateRuntimeCSP())
  response.headers.set('X-Content-Type-Options', 'nosniff')
  response.headers.set('X-Frame-Options', 'SAMEORIGIN')

  return track(request, response)
}

/**
 * Keeps non-production sim.ai deployments out of search results.
 *
 * `noindex` rather than a robots.txt `Disallow` is deliberate: a disallowed URL
 * can still be indexed when linked externally, and blocking the crawl stops
 * search engines from ever seeing the directive that removes pages already in
 * the index. robots.txt is excluded from this proxy's matcher so it keeps
 * serving the crawlable rules this header depends on.
 */
function applyIndexingPolicy(request: NextRequest, response: NextResponse): void {
  const host =
    request.headers.get('x-forwarded-host')?.split(',')[0]?.trim() ||
    request.headers.get('host') ||
    request.nextUrl.host

  if (isNonCanonicalSimHost(host)) {
    response.headers.set('X-Robots-Tag', 'noindex, nofollow')
  }
}

/**
 * Sends request data to Profound analytics (fire-and-forget) and returns the response.
 */
function track(request: NextRequest, response: NextResponse): NextResponse {
  applyIndexingPolicy(request, response)
  sendToProfound(request, response.status)
  return response
}

export const config = {
  matcher: [
    '/', // Root path for self-hosted redirect logic
    '/terms', // Whitelabel terms redirect
    '/privacy', // Whitelabel privacy redirect
    '/w', // Legacy /w redirect
    '/w/:path*', // Legacy /w/* redirects
    '/workspace/:path*', // New workspace routes
    '/login',
    '/signup',
    '/auth/:path*', // Same-origin LingxiIdentity BFF callback and Experience routes
    '/api/:path*', // Runtime CORS
    // Catch-all for other pages, excluding static assets and public directories.
    // The `ingest` exclusion was removed with the fake analytics route (#48).
    '/((?!api/|api$|_next/static|_next/image|favicon.ico|logo/|landing/|static/|footer/|social/|enterprise/|favicon/|twitter/|robots.txt|sitemap.xml).*)',
  ],
}
