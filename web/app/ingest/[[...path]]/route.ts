export const dynamic = 'force-static'
export const revalidate = 3600

export function generateStaticParams() {
  return [{ path: ['disabled'] }]
}

/**
 * Sim's analytics proxy is intentionally not shipped with the Lingxi static
 * frontend. Keeping a deterministic response preserves the route shape while
 * preventing the browser build from proxying data to an external service.
 */
export function GET() {
  return new Response(
    JSON.stringify({
      enabled: false,
      code: 'NOT_INTEGRATED',
      message: '分析服务尚未接入 LingxiGraph',
    }),
    {
      status: 404,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, max-age=3600',
      },
    }
  )
}
