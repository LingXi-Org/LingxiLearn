import { SITE_URL } from '@/lib/urls'

export const dynamic = 'force-static'
export const revalidate = 86400

export async function GET() {
  const xml = `<?xml version="1.0" encoding="UTF-8" ?>
      <rss version="2.0">
        <channel>
          <title>灵犀智学更新日志</title>
          <link>${SITE_URL}/changelog</link>
          <description>灵犀智学学习工作台的版本更新与能力接入记录。</description>
          <language>zh-cn</language>
        </channel>
      </rss>`

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': `public, max-age=${revalidate}, s-maxage=${revalidate}`,
    },
  })
}
