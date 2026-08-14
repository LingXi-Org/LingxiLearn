import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { ImageResponse } from 'next/og'

const size = {
  width: 1200,
  height: 630,
}

const TITLE_FONT_SIZE = {
  large: 64,
  medium: 56,
  small: 48,
} as const

function getTitleFontSize(title: string): number {
  if (title.length > 42) return TITLE_FONT_SIZE.small
  if (title.length > 26) return TITLE_FONT_SIZE.medium
  return TITLE_FONT_SIZE.large
}

/**
 * Geist, read from the repo rather than fetched from Google Fonts.
 *
 * Satori requires at least one font and throws if it gets none, so a fetch that
 * returned nothing took the whole build down with "No fonts are loaded" on
 * whichever page happened to be rendering. That was not a rare race: six routes
 * build an OG image, `integrations/[slug]` alone is 237 pages, and each render
 * fetched two weights subsetted by `&text=` — a per-page URL no cache can reuse.
 * Several hundred uncacheable requests to one host, from one CI egress IP, in
 * parallel across build workers.
 *
 * Read once at module scope, per Next's `ImageResponse` guidance. `.ttf`
 * because Satori accepts only ttf/otf/woff — the sibling `.woff2` the app
 * serves to browsers cannot be reused here.
 *
 * These live under `public/` so they need no `outputFileTracingIncludes` entry:
 * `web/Dockerfile` copies that directory into the static-export runner, which the
 * `force-dynamic` share-token card needs since it renders per request.
 *
 * `process.cwd()` is the app directory in every environment this runs in, not
 * just dev and build. The container starts at the monorepo root, but Next's
 * generated standalone `server.js` opens with `process.chdir(__dirname)`, and
 * that file ships beside `public/` — which is also why `content/` is read this
 * way at runtime.
 */
const FONT_DIR = join(process.cwd(), 'public', 'brand', 'fonts')

const [geistRegular, geistMedium] = await Promise.all([
  readFile(join(FONT_DIR, 'Geist-Regular.ttf')),
  readFile(join(FONT_DIR, 'Geist-Medium.ttf')),
])

interface LandingOgImageProps {
  eyebrow: string
  title: string
  subtitle: string
  pills?: string[]
  domainLabel?: string
}

function escapeXml(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (character) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[character] ??
      character
  )
}

function createStaticOgImage({ eyebrow, title, subtitle, domainLabel }: LandingOgImageProps) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="#121212"/>
  <text x="64" y="110" fill="#71717a" font-family="Arial, sans-serif" font-size="22">${escapeXml(eyebrow)}</text>
  <text x="64" y="205" fill="#fafafa" font-family="Arial, sans-serif" font-size="64" font-weight="600">${escapeXml(title)}</text>
  <text x="64" y="275" fill="#a1a1aa" font-family="Arial, sans-serif" font-size="28">${escapeXml(subtitle)}</text>
  <text x="64" y="570" fill="#fafafa" font-family="Arial, sans-serif" font-size="28" font-weight="600">LingxiGraph</text>
  <text x="1136" y="570" text-anchor="end" fill="#71717a" font-family="Arial, sans-serif" font-size="20">${escapeXml(domainLabel ?? 'lingxilearn.cn')}</text>
</svg>`
  return new Response(svg, { headers: { 'Content-Type': 'image/svg+xml' } })
}

/** Shared dynamic OG image for landing catalog pages (models, integrations). */
export async function createLandingOgImage({
  eyebrow,
  title,
  subtitle,
  pills = [],
  domainLabel = 'lingxilearn.cn',
}: LandingOgImageProps) {
  // `next/og` relies on libvips on Windows, where the integration catalog
  // build can fail before any Lingxi workspace code is evaluated. The static
  // SVG is already the production export fallback, so use it for local
  // Windows builds as well.
  if (process.env.NEXT_STATIC_EXPORT === '1' || process.platform === 'win32') {
    return createStaticOgImage({
      eyebrow,
      title,
      subtitle,
      domainLabel: domainLabel ?? 'lingxilearn.cn',
    })
  }

  return new ImageResponse(
    <div
      style={{
        height: '100%',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '56px 64px',
        background: '#121212',
        fontFamily: 'Geist',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <span
          style={{
            fontSize: 22,
            fontWeight: 500,
            color: '#71717a',
            letterSpacing: '-0.01em',
          }}
        >
          {eyebrow}
        </span>

        <span
          style={{
            fontSize: getTitleFontSize(title),
            fontWeight: 500,
            color: '#fafafa',
            lineHeight: 1.08,
            letterSpacing: '-0.03em',
            maxWidth: '1000px',
          }}
        >
          {title}
        </span>

        <span
          style={{
            fontSize: 28,
            fontWeight: 400,
            color: '#a1a1aa',
            lineHeight: 1.35,
            maxWidth: '980px',
          }}
        >
          {subtitle}
        </span>

        {pills.length > 0 ? (
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 4 }}>
            {pills.slice(0, 4).map((pill) => (
              <div
                key={pill}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  borderRadius: 9999,
                  border: '1px solid #2f2f2f',
                  background: '#1b1b1b',
                  padding: '10px 16px',
                  color: '#d4d4d8',
                  fontSize: 20,
                  fontWeight: 500,
                }}
              >
                {pill}
              </div>
            ))}
          </div>
        ) : null}
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          width: '100%',
        }}
      >
        <span
          style={{
            color: '#fafafa',
            fontSize: 28,
            fontWeight: 500,
          }}
        >
          LingxiGraph
        </span>
        <span
          style={{
            fontSize: 20,
            fontWeight: 400,
            color: '#71717a',
          }}
        >
          {domainLabel}
        </span>
      </div>
    </div>,
    {
      ...size,
      fonts: [
        { name: 'Geist', data: geistRegular, style: 'normal' as const, weight: 400 as const },
        { name: 'Geist', data: geistMedium, style: 'normal' as const, weight: 500 as const },
      ],
    }
  )
}
