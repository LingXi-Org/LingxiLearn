import Image from 'next/image'

/** Letter-based LingXi brand mark used only by marketing/introduction pages. */
export function LingxiWordmark() {
  return (
    <Image
      src='/lingxi-wordmark-primary.svg'
      alt='LingXi'
      width={76}
      height={33}
      priority
      className='h-[24px] w-auto'
    />
  )
}
