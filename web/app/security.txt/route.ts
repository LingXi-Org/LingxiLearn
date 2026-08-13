export const dynamic = 'force-static'
export const revalidate = 86400

export function GET() {
  return new Response('# Lingxi security policy is published at /.well-known/security.txt\n', {
    status: 404,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=86400',
    },
  })
}
