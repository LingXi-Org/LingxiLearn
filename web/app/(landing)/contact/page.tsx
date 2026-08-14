import type { Metadata } from 'next'
import Contact from './contact'

export const metadata: Metadata = {
  title: '联系我们 · LingXi',
  description: '联系 LingXi 技术与产品团队，交流面向学生的 AI 学习 Agent。',
}

// Keep the contact card markup from being held by the production cache for a year.
export const revalidate = 3600

export default function Page() {
  return <Contact />
}
