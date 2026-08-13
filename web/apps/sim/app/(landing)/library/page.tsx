import type { Metadata } from 'next'
import { selectVisiblePosts } from '@/lib/content/index-list'
import { getAllPostMeta } from '@/lib/library/registry'
import { buildCollectionPageJsonLd, buildIndexMetadata, LIBRARY_SECTION } from '@/lib/library/seo'
import { ContentIndexPage } from '@/app/(landing)/components'

/**
 * Filtered/paginated variants render genuinely different lists, but only the
 * bare index is indexable — see `buildIndexMetadata` in `@/lib/content/seo`
 * for the shared noindex policy.
 */
export async function generateMetadata(): Promise<Metadata> {
  return buildIndexMetadata({ pageNum: 1 })
}

export default async function LibraryIndex() {
  const pageNum = 1
  const tag = undefined
  const posts = await getAllPostMeta()

  return (
    <ContentIndexPage
      basePath={LIBRARY_SECTION.basePath}
      heading='The Sim Library'
      subheading={LIBRARY_SECTION.description}
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
