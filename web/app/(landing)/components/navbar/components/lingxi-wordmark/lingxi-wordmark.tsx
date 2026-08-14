import Image from 'next/image'
import { LINGXI_BRAND_ASSETS } from '@/lib/branding/lingxi-assets'

/** Theme-aware LingXi wordmark for light and dark surfaces. */
export function LingxiWordmark() {
  return (
    <>
      <Image
        src={LINGXI_BRAND_ASSETS.wordmarkOnLight}
        alt='LingXi'
        width={76}
        height={33}
        priority
        className='h-[24px] w-auto dark:hidden'
      />
      <Image
        src={LINGXI_BRAND_ASSETS.wordmarkOnDark}
        alt=''
        width={76}
        height={33}
        priority
        aria-hidden='true'
        className='hidden h-[24px] w-auto dark:block'
      />
    </>
  )
}
