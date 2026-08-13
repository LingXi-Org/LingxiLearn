import type { Metadata } from 'next'
import { NotIntegrated } from '@/ee/not-integrated'

export const metadata: Metadata = { title: '验证邮箱' }

export default function VerifyPage() {
  return <NotIntegrated title='邮箱验证' />
}
