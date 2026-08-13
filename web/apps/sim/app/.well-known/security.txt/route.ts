export const dynamic = 'force-static'
export const revalidate = 86400

export async function GET() {
  const securityTxt = `# Lingxi Security Policy
# https://securitytxt.org/
# RFC 9116: https://www.rfc-editor.org/rfc/rfc9116.html

# Required: Contact information for security reports
Contact: mailto:security@lingxi.local

# Required: When this file expires (ISO 8601 format, within 1 year)
Expires: 2099-12-31T23:59:59.000Z

# Preferred languages for security reports
Preferred-Languages: zh, en

# If you discover a security vulnerability, please report it responsibly.
# We appreciate your help in keeping Lingxi and our users secure.
`

  return new Response(securityTxt, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=86400',
    },
  })
}
