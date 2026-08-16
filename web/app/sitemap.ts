import type { MetadataRoute } from 'next'
import { getAllPostMeta as getAllBlogPostMeta } from '@/lib/blog/registry'
import { latestModified } from '@/lib/content/utils'
import { getAllPostMeta as getAllLibraryPostMeta } from '@/lib/library/registry'
import { SITE_URL } from '@/lib/urls'

export const dynamic = 'force-static'
export const revalidate = 86400

const STATIC_PATHS = [
  '/',
  '/learning',
  '/learning/companion',
  '/learning/diagnosis',
  '/learning/explanation',
  '/learning/homework',
  '/learning/personalized',
  '/learning/practice',
  '/safety',
  '/safety/harness',
  '/safety/data-compliance',
  '/knowledge',
  '/workflows',
  '/tables',
  '/files',
  '/logs',
  '/pricing',
  '/demo',
  '/contact',
  '/careers',
  '/enterprise',
  '/integrations',
  '/models',
  '/comparisons',
  '/terms',
  '/privacy',
]

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [blogPosts, libraryPosts] = await Promise.all([
    getAllBlogPostMeta(),
    getAllLibraryPostMeta(),
  ])
  const blogDate = latestModified(blogPosts)
  const libraryDate = latestModified(libraryPosts)

  return [
    ...STATIC_PATHS.map((path) => ({ url: `${SITE_URL}${path}` })),
    { url: `${SITE_URL}/blog`, lastModified: blogDate },
    { url: `${SITE_URL}/blog/tags`, lastModified: blogDate },
    ...blogPosts.map((post) => ({
      url: post.canonical,
      lastModified: new Date(post.updated ?? post.date),
    })),
    { url: `${SITE_URL}/library`, lastModified: libraryDate },
    { url: `${SITE_URL}/library/tags`, lastModified: libraryDate },
    ...libraryPosts.map((post) => ({
      url: post.canonical,
      lastModified: new Date(post.updated ?? post.date),
    })),
  ]
}
