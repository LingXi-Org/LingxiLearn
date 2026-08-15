import { ProfileCard } from '@/app/(landing)/contact/components/profile-card'

/** Contact page with the LingXi team introduction and interactive profile cards. */
export default function Contact() {
  return (
    <main id='main-content'>
      <section
        id='contact'
        aria-labelledby='contact-heading'
        className='mx-auto w-full max-w-[1460px] px-20 pt-28 pb-24 max-sm:px-5 max-sm:pt-16 max-sm:pb-16 max-lg:px-8'
      >
        <div className='mx-auto flex max-w-[720px] flex-col items-center gap-5 text-center'>
          <p className='sr-only'>
            联系 LingXi 团队，认识技术负责人李承阳和产品负责人李远洋，了解面向学生的 AI 学习 Agent。
          </p>

          <h1
            id='contact-heading'
            className='text-balance text-[52px] text-[var(--text-primary)] leading-[1.08] max-sm:text-[36px]'
          >
            联系我们
          </h1>
          <p className='max-w-[46ch] text-pretty text-[var(--text-body)] text-lg leading-[1.6] max-sm:text-base'>
            LingXi 面向学生提供 AI
            学习支持。欢迎联系技术与产品团队，交流产品体验、合作想法或使用反馈。
          </p>
        </div>

        <div className='mx-auto mt-20 grid w-full max-w-[980px] grid-cols-2 gap-8 max-md:mt-14 max-md:grid-cols-1 max-sm:gap-6'>
          <ProfileCard
            name='李承阳'
            title='技术负责人'
            handle='chengyang.li'
            status='LingXi Engineering'
            avatarUrl='/landing/contact/portrait-li-chengyang.webp'
            iconUrl='/landing/contact/code-icon.svg'
            contactHref='mailto:team@lingxilearn.cn'
          />
          <ProfileCard
            name='李远洋'
            title='产品负责人'
            handle='yuanyang.li'
            status='LingXi Product'
            avatarUrl='/landing/contact/portrait-li-yuanyang.webp'
            iconUrl='/landing/contact/product-icon.svg'
            contactHref='mailto:team@lingxilearn.cn'
          />
        </div>
      </section>
    </main>
  )
}
