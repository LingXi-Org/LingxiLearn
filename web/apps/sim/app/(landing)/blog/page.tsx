import type { Metadata } from 'next'
import { getAllPostMeta } from '@/lib/blog/registry'
import { BLOG_SECTION, buildCollectionPageJsonLd, buildIndexMetadata } from '@/lib/blog/seo'
import { selectVisiblePosts } from '@/lib/content/index-list'
import { ContentIndexPage } from '@/app/(landing)/components'

/**
 * Filtered/paginated variants render genuinely different lists, but only the
 * bare index is indexable — see `buildIndexMetadata` in `@/lib/content/seo`
 * for the shared noindex policy.
 */
export async function generateMetadata(): Promise<Metadata> {
  return buildIndexMetadata({ pageNum: 1 })
}

export default async function BlogIndex() {
  const pageNum = 1
  const tag = undefined
  const posts = await getAllPostMeta()

  return (
    <ContentIndexPage
      basePath={BLOG_SECTION.basePath}
      heading='Latest from Sim'
      subheading={BLOG_SECTION.description}
      posts={posts}
      page={pageNum}
      tag={tag}
      collectionJsonLd={buildCollectionPageJsonLd(
        selectVisiblePosts(posts, { tag, page: pageNum }),
        { tag, page: pageNum }
      )}
    />
  )
}
